import os
import re
import time
import json
import asyncio
import hashlib
from collections import deque
from typing import Dict, List, Optional, Any, Callable
import numpy as np

from shared.schemas.protocol import (
    HEADER_SIZE,
    MSG_TYPE_ACK,
    NeuroPulsePacket,
)
try:
    from ...adapters.piezo import PiezoAdapter
    from ...adapters.adxl345 import ADXL345Adapter
    from ..simulation.simulator import SignalSimulator
except (ImportError, ValueError):
    from backend.app.adapters.piezo import PiezoAdapter
    from backend.app.adapters.adxl345 import ADXL345Adapter
    from backend.app.services.simulation.simulator import SignalSimulator

try:
    import serial
    import serial.tools.list_ports
    HAS_PYSERIAL = True
except ImportError:
    HAS_PYSERIAL = False

try:
    import h5py
    HAS_H5PY = True
except ImportError:
    HAS_H5PY = False

class AcquisitionManager:
    def __init__(self, data_root: str = "./data"):
        self.data_root = os.path.abspath(data_root)
        self.piezo_adapter = PiezoAdapter()
        self.adxl_adapter = ADXL345Adapter()

        self.is_connected = False
        self.is_streaming = False
        self.is_simulated = True
        self.selected_sensor = "PIEZO_LDT0_028K"
        self.current_port = "SIMULATOR"
        self.baud_rate = 115200
        self.simulator_profile = "healthy"
        self.analysis_channel: Optional[str] = None

        # Physical serial handle
        self._serial_handle = None
        self._reader_task: Optional[asyncio.Task] = None
        self._reader_loop: Optional[asyncio.AbstractEventLoop] = None
        self.last_reader_error: Optional[str] = None
        self._simulator: Optional[SignalSimulator] = None

        # Live circular buffers (keeps last 8 seconds of data for live display)
        self.max_buffer_samples = 8000
        self.live_channels: Dict[str, deque] = {
            "raw_counts": deque(maxlen=self.max_buffer_samples),
            "x_counts": deque(maxlen=self.max_buffer_samples),
            "y_counts": deque(maxlen=self.max_buffer_samples),
            "z_counts": deque(maxlen=self.max_buffer_samples),
            "x": deque(maxlen=self.max_buffer_samples),
            "y": deque(maxlen=self.max_buffer_samples),
            "z": deque(maxlen=self.max_buffer_samples),
            "mag": deque(maxlen=self.max_buffer_samples),
        }

        # Diagnostics counters
        self.total_packets_received = 0
        self.total_samples_received = 0
        self.packet_crc_errors = 0
        self.malformed_packets = 0
        self.timestamp_errors = 0
        self.sequence_gaps = 0
        self.last_seq_num: Optional[int] = None
        self.start_stream_time: Optional[float] = None
        self.effective_sample_rate = 0.0
        self.sample_timing_status = "UNMEASURED"
        self.sample_rate_source: Optional[str] = None
        self.first_sample_timestamp_us: Optional[int] = None
        self._last_packet_timestamp_us: Optional[int] = None
        self._rate_anchor_timestamp_us: Optional[int] = None
        self._rate_anchor_sequence: Optional[int] = None

        # Active recording session
        self.active_session_id: Optional[str] = None
        self.session_raw_samples: Dict[str, List[float]] = {}
        self.session_start_monotonic_us: int = 0

        # Event callbacks (e.g. WebSocket subscribers)
        self.listeners: List[Callable[[Dict[str, Any]], None]] = []

    def get_available_ports(self) -> List[Dict[str, str]]:
        ports = [{"port": "SIMULATOR", "description": "NeuroPulse Virtual Signal Simulator"}]
        if HAS_PYSERIAL:
            try:
                for p in serial.tools.list_ports.comports():
                    ports.append({"port": p.device, "description": p.description or p.device})
            except Exception:
                pass
        return ports

    def connect(self, port: str = "SIMULATOR", baud_rate: int = 115200, sensor_type: str = "PIEZO_LDT0_028K",
                simulator_profile: str = "healthy"):
        if self.is_connected:
            if self.is_streaming:
                raise RuntimeError("Stop the active acquisition before changing device connections.")
            self.disconnect()

        self.current_port = port
        self.baud_rate = baud_rate
        self.selected_sensor = sensor_type
        self.is_simulated = (port == "SIMULATOR")
        if simulator_profile not in {"healthy", "volatile"}:
            raise ValueError("Simulator profile must be healthy or volatile.")
        self.simulator_profile = simulator_profile

        if self.is_simulated:
            self.is_connected = True
            return {"status": "connected", "port": port, "mode": "simulated", "sensor": sensor_type,
                    "simulator_profile": self.simulator_profile}

        if not HAS_PYSERIAL:
            raise RuntimeError("pyserial is not installed; cannot open physical serial port.")

        try:
            self._serial_handle = serial.Serial(port, baudrate=baud_rate, timeout=0.1)
            # Opening an ESP32 USB serial port commonly triggers an auto-reset.
            # Wait for its boot before sending the sensor selection command.
            time.sleep(2.0)
            # Keep firmware configuration aligned with the host-side adapter.
            # Firmware responses are framed ACK packets and are filtered by msg_type.
            self._serial_handle.reset_input_buffer()
            sensor_command = b"SELECT_SENSOR ADXL345\n" if sensor_type == "ADXL345" else b"SELECT_SENSOR PIEZO\n"
            self._serial_handle.write(sensor_command)
            response = self._read_serial_frame(timeout_sec=2.0)
            if response is None or response.msg_type != MSG_TYPE_ACK or response.payload != b"OK":
                raise RuntimeError("Firmware did not acknowledge the requested sensor configuration.")
            self.is_connected = True
            return {"status": "connected", "port": port, "mode": "hardware", "sensor": sensor_type}
        except Exception as e:
            self.is_connected = False
            if self._serial_handle:
                try:
                    self._serial_handle.close()
                except Exception:
                    pass
                self._serial_handle = None
            raise RuntimeError(f"Failed to open port {port}: {e}")

    def _read_serial_frame(self, timeout_sec: float) -> Optional[NeuroPulsePacket]:
        """Read one complete framed response while preserving byte alignment."""
        deadline = time.monotonic() + timeout_sec
        buffer = bytearray()
        while time.monotonic() < deadline:
            waiting = self._serial_handle.in_waiting if self._serial_handle else 0
            chunk = self._serial_handle.read(max(1, waiting)) if self._serial_handle else b""
            if chunk:
                buffer.extend(chunk)
            while len(buffer) >= 2 and buffer[:2] != b"\xAA\x55":
                del buffer[0]
            if len(buffer) < HEADER_SIZE:
                continue
            payload_len = buffer[4] | (buffer[5] << 8)
            total_len = HEADER_SIZE + payload_len + 2
            if len(buffer) < total_len:
                continue
            packet, _error = NeuroPulsePacket.decode(bytes(buffer[:total_len]))
            return packet
        return None

    async def disconnect_async(self):
        if self.is_streaming or self.active_session_id:
            await self.stop_acquisition_async()
        if self._serial_handle and self._serial_handle.is_open:
            try:
                self._serial_handle.close()
            except Exception:
                pass
        self._serial_handle = None
        self.is_connected = False
        return {"status": "disconnected"}

    def disconnect(self):
        if not self.is_streaming and not self.active_session_id:
            if self._serial_handle and self._serial_handle.is_open:
                try:
                    self._serial_handle.close()
                except Exception:
                    pass
            self._serial_handle = None
            self.is_connected = False
            return {"status": "disconnected"}
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(self.disconnect_async())
        raise RuntimeError("disconnect() cannot block an active event loop; use disconnect_async().")

    def start_acquisition(self, session_id: Optional[str] = None):
        if not self.is_connected:
            raise RuntimeError("Cannot start acquisition: Device is not connected.")
        if self.is_streaming:
            return {"status": "already_streaming"}

        if session_id is not None:
            if not re.fullmatch(r"[A-Za-z0-9_-]{1,80}", session_id):
                raise RuntimeError("Invalid session ID; expected 1-80 letters, numbers, '_' or '-'.")
            existing_dir = os.path.join(self.data_root, "sessions", session_id)
            if any(os.path.exists(os.path.join(existing_dir, name)) for name in ("raw.json", "raw.h5")):
                raise RuntimeError("Raw recording already exists for this session ID and cannot be overwritten.")

        self.is_streaming = True
        self._reader_loop = asyncio.get_running_loop()
        self.start_stream_time = time.perf_counter()
        self.total_packets_received = 0
        self.total_samples_received = 0
        self.sequence_gaps = 0
        self.packet_crc_errors = 0
        self.malformed_packets = 0
        self.timestamp_errors = 0
        self.last_seq_num = None
        self.last_reader_error = None
        self.effective_sample_rate = 0.0
        self.sample_timing_status = "AWAITING_DEVICE_TIMESTAMPS" if not self.is_simulated else "SIMULATED_CONFIGURED"
        self.sample_rate_source = None
        self.first_sample_timestamp_us = None
        self._last_packet_timestamp_us = None
        self._rate_anchor_timestamp_us = None
        self._rate_anchor_sequence = None
        # Live analysis must never carry samples over from a previous session.
        for channel_buffer in self.live_channels.values():
            channel_buffer.clear()

        # Reset session storage if recording
        self.active_session_id = session_id
        if session_id:
            channels = ["raw_counts"] if self.selected_sensor == "PIEZO_LDT0_028K" else ["x_counts", "y_counts", "z_counts"]
            self.session_raw_samples = {channel: [] for channel in channels}
            self.session_start_monotonic_us = 0

        # Launch background acquisition task
        if self.is_simulated:
            scenario = {
                "healthy": {"tremor_freq_hz": 2.0, "tremor_amp": 18.0, "noise_amp": 12.0},
                "volatile": {"tremor_freq_hz": 5.0, "tremor_amp": 250.0, "noise_amp": 25.0},
            }[self.simulator_profile]
            self._simulator = SignalSimulator(
                sensor_type=self.selected_sensor,
                sample_rate_hz=1000.0 if self.selected_sensor == "PIEZO_LDT0_028K" else 100.0,
                **scenario,
            )
            self.effective_sample_rate = self._simulator.sample_rate_hz
            self.sample_timing_status = "SIMULATED_CONFIGURED"
            self.sample_rate_source = "simulator_configuration"
            self._reader_task = asyncio.create_task(self._simulation_loop())
        else:
            self._reader_task = asyncio.create_task(self._hardware_serial_loop())

        return {"status": "streaming_started", "session_id": session_id, "mode": "simulated" if self.is_simulated else "hardware"}

    async def stop_acquisition_async(self):
        self.is_streaming = False
        if self._simulator:
            self._simulator.stop()
        task = self._reader_task
        if task:
            if not task.done():
                task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
            except Exception as exc:
                self.last_reader_error = str(exc)
        self._reader_task = None
        self._reader_loop = None

        return self._finalize_recording()

    def _finalize_recording(self):
        # Save only after the reader task has stopped, so the raw file is immutable.
        saved_file_info = None
        if self.active_session_id and self.session_raw_samples:
            saved_file_info = self._persist_session_data(self.active_session_id)
            self.active_session_id = None
            self.session_raw_samples = {}

        return {"status": "streaming_stopped", "saved_recording": saved_file_info}

    def stop_acquisition(self):
        if not self._reader_task or self._reader_task.done():
            self.is_streaming = False
            if self._simulator:
                self._simulator.stop()
            self._reader_task = None
            self._reader_loop = None
            return self._finalize_recording()
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(self.stop_acquisition_async())
        raise RuntimeError("stop_acquisition() cannot block an active event loop; use stop_acquisition_async().")

    def _persist_session_data(self, session_id: str) -> Dict[str, Any]:
        session_dir = os.path.join(self.data_root, "sessions", session_id)
        os.makedirs(session_dir, exist_ok=True)
        raw_json_path = os.path.join(session_dir, "raw.json")
        raw_h5_path = os.path.join(session_dir, "raw.h5")

        if self.is_simulated:
            sample_rate = self._simulator.sample_rate_hz if self._simulator else self.effective_sample_rate or None
            sample_timing_status = "SIMULATED_CONFIGURED"
            sample_rate_source = "simulator_configuration"
        elif self.sample_timing_status in {"MEASURED_DEVICE_TIMESTAMPS", "SAMPLE_GAPS"} and self.effective_sample_rate > 0:
            sample_rate = self.effective_sample_rate
            sample_timing_status = self.sample_timing_status
            sample_rate_source = "device_monotonic_timestamps_and_sequence"
        else:
            sample_rate = None
            sample_timing_status = self.sample_timing_status
            sample_rate_source = None
        provenance_val = "simulated" if self.is_simulated else "device"

        channel_units = {
            "raw_counts": "esp32_adc_counts",
            "x_counts": "adxl345_register_counts",
            "y_counts": "adxl345_register_counts",
            "z_counts": "adxl345_register_counts",
        }

        payload = {
            "session_id": session_id,
            "sensor_type": self.selected_sensor,
            "provenance": provenance_val,
            "sample_rate_hz": sample_rate,
            "sample_timing_status": sample_timing_status,
            "sample_rate_source": sample_rate_source,
            "timestamp_start_monotonic_us": self.session_start_monotonic_us,
            "total_samples": self.total_samples_received,
            "sequence_gaps": self.sequence_gaps,
            "packet_crc_errors": self.packet_crc_errors,
            "malformed_packets": self.malformed_packets,
            "timestamp_errors": self.timestamp_errors,
            "simulator_profile": self.simulator_profile if self.is_simulated else None,
            "simulator_parameters": ({
                "tremor_freq_hz": self._simulator.tremor_freq_hz,
                "tremor_amplitude": self._simulator.tremor_amp,
                "noise_amplitude": self._simulator.noise_amp,
            } if self.is_simulated and self._simulator else None),
            "channel_units": {key: channel_units[key] for key in self.session_raw_samples if key in channel_units},
            "channels": self.session_raw_samples
        }

        canonical_payload = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        sha256_hash = hashlib.sha256(canonical_payload).hexdigest()
        payload["sha256"] = sha256_hash
        data_bytes = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")

        with open(raw_json_path, "xb") as f:
            f.write(data_bytes)

        # HDF5 binary raw storage (STORE-01 & D-013)
        h5_written = False
        if HAS_H5PY:
            try:
                with h5py.File(raw_h5_path, "x") as h5f:
                    h5f.attrs["session_id"] = str(session_id)
                    h5f.attrs["sensor_type"] = str(self.selected_sensor)
                    h5f.attrs["provenance"] = str(provenance_val)
                    if sample_rate is not None:
                        h5f.attrs["sample_rate_hz"] = float(sample_rate)
                    h5f.attrs["sample_timing_status"] = sample_timing_status
                    h5f.attrs["sample_rate_source"] = sample_rate_source or "unavailable"
                    h5f.attrs["timestamp_start_monotonic_us"] = int(self.session_start_monotonic_us)
                    h5f.attrs["total_samples"] = int(self.total_samples_received)
                    h5f.attrs["sequence_gaps"] = int(self.sequence_gaps)
                    h5f.attrs["packet_crc_errors"] = int(self.packet_crc_errors)
                    h5f.attrs["malformed_packets"] = int(self.malformed_packets)
                    h5f.attrs["timestamp_errors"] = int(self.timestamp_errors)
                    if self.is_simulated and self._simulator:
                        h5f.attrs["simulator_profile"] = self.simulator_profile
                        h5f.attrs["simulator_parameters_json"] = json.dumps(payload["simulator_parameters"], sort_keys=True)
                    h5f.attrs["channel_units_json"] = json.dumps(payload["channel_units"], sort_keys=True)
                    h5f.attrs["sha256_json"] = str(sha256_hash)

                    chan_grp = h5f.create_group("channels")
                    for ch_name, samples in self.session_raw_samples.items():
                        arr = np.asarray(samples, dtype=np.float32)
                        chan_grp.create_dataset(ch_name, data=arr, compression="gzip", compression_opts=4)
                h5_written = True
            except Exception:
                h5_written = False
                if os.path.exists(raw_h5_path):
                    try:
                        os.remove(raw_h5_path)
                    except OSError:
                        pass

        primary_file = raw_h5_path if h5_written else raw_json_path
        return {
            "session_id": session_id,
            "file_path": primary_file,
            "raw_json_path": raw_json_path,
            "raw_h5_path": raw_h5_path if h5_written else None,
            "sha256": sha256_hash,
            "total_samples": self.total_samples_received,
            "sample_rate_hz": sample_rate,
            "sample_timing_status": sample_timing_status,
            "sample_rate_source": sample_rate_source,
            "timestamp_start_monotonic_us": self.session_start_monotonic_us,
            "sequence_gaps": self.sequence_gaps,
            "sensor_type": self.selected_sensor
        }

    async def _simulation_loop(self):
        try:
            async for packet in self._simulator.generate_stream():
                if not self.is_streaming:
                    break
                self._ingest_packet(packet)
        except asyncio.CancelledError:
            pass

    async def _hardware_serial_loop(self):
        # Hardware continuous binary frame reader with frame alignment
        try:
            # Send START_STREAM command to MCU
            self._serial_handle.write(b"START_STREAM\n")
            buffer = bytearray()
            while self.is_streaming:
                if self._serial_handle.in_waiting:
                    chunk = self._serial_handle.read(self._serial_handle.in_waiting)
                    buffer.extend(chunk)
                    # Find sync header 0xAA 0x55
                    while len(buffer) >= 18:
                        if buffer[0] == 0xAA and buffer[1] == 0x55:
                            payload_len = buffer[4] | (buffer[5] << 8)
                            total_len = 18 + payload_len + 2
                            if len(buffer) < total_len:
                                break # Wait for more bytes
                            frame = bytes(buffer[:total_len])
                            buffer = buffer[total_len:]
                            packet, err = NeuroPulsePacket.decode(frame)
                            if packet:
                                if packet.proto_ver != 1:
                                    self.malformed_packets += 1
                                    continue
                                expected_type = 0x03 if self.selected_sensor == "ADXL345" else 0x02
                                if packet.msg_type == expected_type:
                                    expected_alignment = 6 if expected_type == 0x03 else 2
                                    if packet.payload and len(packet.payload) % expected_alignment == 0:
                                        self._ingest_packet(packet)
                                    else:
                                        self.malformed_packets += 1
                                elif packet.msg_type in (0x02, 0x03):
                                    self.malformed_packets += 1
                            elif err and "CRC mismatch" in err:
                                self.packet_crc_errors += 1
                            else:
                                self.malformed_packets += 1
                        else:
                            # Discard byte to search for sync
                            buffer.pop(0)
                await asyncio.sleep(0.002)
        except asyncio.CancelledError:
            if self._serial_handle and self._serial_handle.is_open:
                try:
                    self._serial_handle.write(b"STOP_STREAM\n")
                except Exception:
                    pass
        except Exception as exc:
            # Keep the session stoppable so samples already received can be finalized.
            self.last_reader_error = f"Serial acquisition failed: {exc}"

    def _ingest_packet(self, packet: NeuroPulsePacket):
        previous_sequence = self.last_seq_num
        previous_timestamp_us = self._last_packet_timestamp_us
        if self.last_seq_num is not None:
            sequence_delta = (packet.seq_num - self.last_seq_num) & 0xFFFFFFFF
            # Sequence numbers are per packet. Reject duplicate or stale frames;
            # appending them would distort timing and spectral energy.
            if sequence_delta == 0 or sequence_delta >= 0x80000000:
                self.malformed_packets += 1
                return
            if sequence_delta > 1:
                self.sequence_gaps += sequence_delta - 1
        self.total_packets_received += 1
        self.last_seq_num = packet.seq_num

        adapter = self.piezo_adapter if self.selected_sensor == "PIEZO_LDT0_028K" else self.adxl_adapter
        decoded_data = adapter.decode_raw_payload(packet.payload)

        # Update sample counters & rate
        num_samples = len(next(iter(decoded_data.values()), []))
        self.total_samples_received += num_samples
        if self.first_sample_timestamp_us is None:
            self.first_sample_timestamp_us = packet.timestamp_us
            self.session_start_monotonic_us = packet.timestamp_us

        if self.is_simulated:
            if self._simulator:
                self.effective_sample_rate = float(self._simulator.sample_rate_hz)
            self.sample_timing_status = "SIMULATED_CONFIGURED"
            self.sample_rate_source = "simulator_configuration"
        elif num_samples != 1:
            # Protocol v1 does not declare an in-frame sample interval. Preserve
            # the raw batch but never invent timestamps for its samples.
            self.effective_sample_rate = 0.0
            self.sample_timing_status = "UNRESOLVED_BATCH_TIMING"
            self.sample_rate_source = None
            self._rate_anchor_timestamp_us = None
            self._rate_anchor_sequence = None
        elif previous_timestamp_us is None or previous_sequence is None:
            self._rate_anchor_timestamp_us = packet.timestamp_us
            self._rate_anchor_sequence = packet.seq_num
            self.sample_timing_status = "AWAITING_DEVICE_TIMESTAMPS"
            self.sample_rate_source = "device_monotonic_timestamps_and_sequence"
        elif packet.timestamp_us <= previous_timestamp_us:
            self.timestamp_errors += 1
            self.effective_sample_rate = 0.0
            self.sample_timing_status = "INVALID_DEVICE_TIMESTAMPS"
            self.sample_rate_source = None
            self._rate_anchor_timestamp_us = packet.timestamp_us
            self._rate_anchor_sequence = packet.seq_num
        else:
            if self._rate_anchor_timestamp_us is None or self._rate_anchor_sequence is None:
                self._rate_anchor_timestamp_us = previous_timestamp_us
                self._rate_anchor_sequence = previous_sequence
            elapsed_us = packet.timestamp_us - self._rate_anchor_timestamp_us
            sequence_span = (packet.seq_num - self._rate_anchor_sequence) & 0xFFFFFFFF
            if elapsed_us >= 1_000_000 and sequence_span > 0:
                self.effective_sample_rate = round(sequence_span * 1_000_000 / elapsed_us, 3)
                self.sample_timing_status = "MEASURED_DEVICE_TIMESTAMPS"
                self.sample_rate_source = "device_monotonic_timestamps_and_sequence"
                self._rate_anchor_timestamp_us = packet.timestamp_us
                self._rate_anchor_sequence = packet.seq_num
        self._last_packet_timestamp_us = packet.timestamp_us
        if not self.is_simulated and self.sequence_gaps and self.effective_sample_rate > 0:
            self.sample_timing_status = "SAMPLE_GAPS"

        # Append to live buffer
        for ch, vals in decoded_data.items():
            if ch in self.live_channels:
                self.live_channels[ch].extend(vals)
            if self.active_session_id and ch in self.session_raw_samples:
                self.session_raw_samples[ch].extend(vals)

        # Notify subscribers
        event = {
            "type": "sample_batch",
            "seq": packet.seq_num,
            "timestamp_us": packet.timestamp_us,
            "channels": decoded_data,
            "rate_hz": self.effective_sample_rate,
            "sample_timing_status": self.sample_timing_status,
            "sample_rate_source": self.sample_rate_source,
            "sequence_gaps": self.sequence_gaps,
            "total_samples": self.total_samples_received,
            "is_simulated": self.is_simulated
        }
        for cb in self.listeners:
            try:
                cb(event)
            except Exception:
                pass

    def get_status(self) -> Dict[str, Any]:
        elapsed_sec = (max(0.0, time.perf_counter() - self.start_stream_time)
                       if self.is_streaming and self.start_stream_time is not None else 0.0)
        return {
            "is_connected": self.is_connected,
            "is_streaming": self.is_streaming,
            "is_simulated": self.is_simulated,
            "simulator_profile": self.simulator_profile if self.is_simulated else None,
            "port": self.current_port,
            "baud_rate": self.baud_rate,
            "sensor_type": self.selected_sensor,
            "effective_sample_rate": self.effective_sample_rate,
            "sample_timing_status": self.sample_timing_status,
            "sample_rate_source": self.sample_rate_source,
            "timestamp_start_monotonic_us": self.first_sample_timestamp_us,
            "total_packets": self.total_packets_received,
            "total_samples": self.total_samples_received,
            "sequence_gaps": self.sequence_gaps,
            "crc_errors": self.packet_crc_errors,
            "malformed_packets": self.malformed_packets,
            "active_session_id": self.active_session_id,
            "elapsed_sec": round(elapsed_sec, 1),
            "last_reader_error": self.last_reader_error,
        }

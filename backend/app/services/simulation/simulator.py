import time
import math
import asyncio
from typing import AsyncGenerator, Dict, Any
import numpy as np

from shared.schemas.protocol import (
    NeuroPulsePacket,
    MSG_TYPE_DATA_PIEZO,
    MSG_TYPE_DATA_ADXL,
    encode_piezo_payload,
    encode_adxl_payload,
)

class SignalSimulator:
    def __init__(
        self,
        sensor_type: str = "PIEZO_LDT0_028K",
        sample_rate_hz: float = 1000.0,
        tremor_freq_hz: float = 5.0,
        tremor_amp: float = 250.0,
        noise_amp: float = 25.0,
        batch_size: int = 10
    ):
        self.sensor_type = sensor_type
        self.sample_rate_hz = sample_rate_hz
        self.tremor_freq_hz = tremor_freq_hz
        self.tremor_amp = tremor_amp
        self.noise_amp = noise_amp
        self.batch_size = batch_size
        self._seq = 0
        self._sample_index = 0
        self._running = False
        self._stream_start_monotonic_us = 0

    def start(self):
        self._running = True
        self._seq = 0
        self._sample_index = 0
        self._stream_start_monotonic_us = time.monotonic_ns() // 1000

    def stop(self):
        self._running = False

    async def generate_stream(self) -> AsyncGenerator[NeuroPulsePacket, None]:
        self.start()
        interval = self.batch_size / self.sample_rate_hz
        while self._running:
            start_t = time.perf_counter()
            packet_first_sample_index = self._sample_index
            t_samples = (packet_first_sample_index + np.arange(self.batch_size)) / self.sample_rate_hz
            self._sample_index += self.batch_size

            # Tremor wave (3-6 Hz) + low-frequency drift (0.3 Hz) + noise
            tremor = self.tremor_amp * np.sin(2 * np.pi * self.tremor_freq_hz * t_samples)
            drift = 40.0 * np.sin(2 * np.pi * 0.3 * t_samples)
            noise = np.random.normal(0, self.noise_amp, self.batch_size)

            if self.sensor_type == "PIEZO_LDT0_028K":
                counts = np.clip(2048.0 + tremor + drift + noise, 0, 4095).astype(int).tolist()
                payload = encode_piezo_payload(counts)
                msg_type = MSG_TYPE_DATA_PIEZO
            else:
                # ADXL345: 3 axes (X, Y, Z)
                x = np.clip(tremor + noise, -32768, 32767).astype(int).tolist()
                y = np.clip((tremor * 0.6) + noise, -32768, 32767).astype(int).tolist()
                z = np.clip(256 + (drift * 0.5) + noise, -32768, 32767).astype(int).tolist()
                payload = encode_adxl_payload(x, y, z)
                msg_type = MSG_TYPE_DATA_ADXL

            packet = NeuroPulsePacket(
                msg_type=msg_type,
                seq_num=self._seq,
                timestamp_us=self._stream_start_monotonic_us + round(packet_first_sample_index * 1_000_000 / self.sample_rate_hz),
                payload=payload
            )
            self._seq += 1
            yield packet

            elapsed = time.perf_counter() - start_t
            sleep_time = max(0.0, interval - elapsed)
            await asyncio.sleep(sleep_time)

# Serial Protocol Specification — NeuroPulse MVP

---

## 1. Framing & Wire Format

To guarantee low overhead and data integrity at 1000 Hz sampling rates over USB Serial, NeuroPulse defines a framed binary protocol.

### Binary Frame Structure

```text
+--------+--------+--------+--------+--------+--------+--------+--------+
| 0xAA   | 0x55   | MSG_TY | PROTO  | PAYLOAD_LEN     | SEQ_NUM (uint32) |
+--------+--------+--------+--------+--------+--------+--------+--------+
| TIMESTAMP_US (uint64)             | PAYLOAD BYTES (PAYLOAD_LEN)       |
+-----------------------------------+-----------------------------------+
| ... PAYLOAD DATA ...              | CRC16-CCITT (2 bytes)             |
+--------+--------+--------+--------+--------+--------+--------+--------+
```

| Field | Size (bytes) | Description |
|---|---|---|
| Sync Header | 2 | `0xAA 0x55` |
| Message Type | 1 | `0x01`: HELLO/ACK, `0x02`: DATA_PIEZO, `0x03`: DATA_ADXL, `0x0E`: ERROR, `0x0F`: STATUS |
| Protocol Version | 1 | `0x01` |
| Payload Length | 2 | Little-endian uint16 indicating payload size |
| Sequence Number | 4 | Little-endian uint32 (increments per packet) |
| Monotonic Timestamp | 8 | Little-endian uint64 (microseconds since MCU boot) |
| Payload | N | Channel samples |
| Checksum | 2 | CRC16-CCITT calculated over all preceding bytes |

---

## 2. Command Set (Host to MCU)

ASCII or binary commands sent over serial:
- `HELLO` / `GET_INFO`: MCU replies with firmware version, device ID, sensor type, supported sample rates.
- `GET_STATUS`: MCU replies with current acquisition state, buffer fill level, dropped packet count.
- `SELECT_SENSOR PIEZO` / `SELECT_SENSOR ADXL345`: select the matching sensor driver before acquisition.
- `CONFIGURE <rate_hz> <flags>`: Sets output data rate and hardware settings.
- `START_STREAM`: MCU begins continuous sampling and packet streaming.
- `STOP_STREAM`: MCU safely stops sampling and clears internal queues.
- `PING`: Heartbeat check; MCU responds with `PONG`.

Control replies (`ACK`, `STATUS`, `HELLO`, and `ERROR`) use the same framed packet format. The host must inspect `msg_type` and only pass the selected sensor's `DATA_PIEZO` or `DATA_ADXL` frames to its sensor adapter. A data payload must contain a whole number of channel samples (2 bytes per Piezo ADC count or 6 bytes per ADXL345 XYZ sample); malformed payloads are discarded and counted separately from CRC failures.

The current firmware initializes USB Serial at 115200 baud. Until firmware and host baud negotiation are implemented and verified together, use 115200 baud for physical integration.

## 3. Current throughput limit — release blocker for 1000 Hz Piezo

The current fixed header is 18 bytes; CRC adds 2 bytes and one Piezo ADC count adds 2 bytes. With one sample in each frame, this is 22 bytes/sample. At 1000 samples/s the stream requires about 22,000 bytes/s before any command or USB scheduling overhead. A UART configured for 115200 baud with 8N1 framing has a theoretical payload ceiling of 11,520 bytes/s (10 wire bits per byte), so the current one-sample-per-frame format cannot transport the 1000 Hz Piezo target. Its idealized ceiling is about 523 samples/s before other overhead.

Do not treat the current firmware's `targetSampleRateHz = 1000` or the host's effective-rate display as evidence that 1000 samples/s reaches storage. The acquisition rate must be measured end-to-end. Resolve D-006 with a protocol/timing design (for example, batched samples or a verified higher baud) and then measure loss, actual sample timing, and sustained throughput with the final board and sensor. If batching uses one frame timestamp plus a configured rate to reconstruct in-batch timestamps, validate that timing model against firmware timing; do not silently label reconstructed timestamps as individually measured.

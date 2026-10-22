"""
Binary Protocol Framing and Codec for NeuroPulse ESP32 <-> Host Communication
Zero-dependency implementation using Python struct module.
"""
import struct
from typing import List, Tuple, Optional

# Constants
SYNC_BYTE_1 = 0xAA
SYNC_BYTE_2 = 0x55
PROTOCOL_VERSION = 0x01

# Message Types
MSG_TYPE_HELLO = 0x01
MSG_TYPE_DATA_PIEZO = 0x02
MSG_TYPE_DATA_ADXL = 0x03
MSG_TYPE_ACK = 0x0A
MSG_TYPE_ERROR = 0x0E
MSG_TYPE_STATUS = 0x0F

HEADER_FORMAT = "<BBBBHIQ"  # sync1, sync2, msg_type, proto_ver, payload_len, seq_num, timestamp_us
HEADER_SIZE = struct.calcsize(HEADER_FORMAT)
CRC_SIZE = 2

def compute_crc16_ccitt(data: bytes) -> int:
    """Computes CRC16-CCITT (poly=0x1021, init=0xFFFF)."""
    crc = 0xFFFF
    for byte in data:
        crc ^= (byte << 8)
        for _ in range(8):
            if crc & 0x8000:
                crc = ((crc << 1) ^ 0x1021) & 0xFFFF
            else:
                crc = (crc << 1) & 0xFFFF
    return crc

class NeuroPulsePacket:
    def __init__(
        self,
        msg_type: int,
        seq_num: int,
        timestamp_us: int,
        payload: bytes,
        proto_ver: int = PROTOCOL_VERSION
    ):
        self.msg_type = msg_type
        self.proto_ver = proto_ver
        self.seq_num = seq_num
        self.timestamp_us = timestamp_us
        self.payload = payload

    def encode(self) -> bytes:
        payload_len = len(self.payload)
        header = struct.pack(
            HEADER_FORMAT,
            SYNC_BYTE_1,
            SYNC_BYTE_2,
            self.msg_type,
            self.proto_ver,
            payload_len,
            self.seq_num,
            self.timestamp_us
        )
        data_to_checksum = header + self.payload
        crc = compute_crc16_ccitt(data_to_checksum)
        return data_to_checksum + struct.pack("<H", crc)

    @classmethod
    def decode(cls, raw_bytes: bytes) -> Tuple[Optional["NeuroPulsePacket"], Optional[str]]:
        """
        Decodes a frame. Returns (packet, error_message).
        """
        if len(raw_bytes) < HEADER_SIZE + CRC_SIZE:
            return None, "Packet too short"

        sync1, sync2, msg_type, proto_ver, payload_len, seq_num, timestamp_us = struct.unpack(
            HEADER_FORMAT, raw_bytes[:HEADER_SIZE]
        )

        if sync1 != SYNC_BYTE_1 or sync2 != SYNC_BYTE_2:
            return None, f"Invalid sync bytes: 0x{sync1:02X} 0x{sync2:02X}"

        expected_total_len = HEADER_SIZE + payload_len + CRC_SIZE
        if len(raw_bytes) < expected_total_len:
            return None, f"Incomplete payload: expected {expected_total_len}, got {len(raw_bytes)}"

        payload = raw_bytes[HEADER_SIZE:HEADER_SIZE + payload_len]
        received_crc = struct.unpack("<H", raw_bytes[HEADER_SIZE + payload_len:expected_total_len])[0]
        calculated_crc = compute_crc16_ccitt(raw_bytes[:HEADER_SIZE + payload_len])

        if received_crc != calculated_crc:
            return None, f"CRC mismatch: expected 0x{calculated_crc:04X}, got 0x{received_crc:04X}"

        return cls(
            msg_type=msg_type,
            seq_num=seq_num,
            timestamp_us=timestamp_us,
            payload=payload,
            proto_ver=proto_ver
        ), None

def encode_piezo_payload(samples: List[int]) -> bytes:
    """Encodes list of 12-bit ADC counts (uint16) into little-endian bytes."""
    return struct.pack(f"<{len(samples)}H", *samples)

def decode_piezo_payload(payload: bytes) -> List[int]:
    sample_count = len(payload) // 2
    return list(struct.unpack(f"<{sample_count}H", payload))

def encode_adxl_payload(x_samples: List[int], y_samples: List[int], z_samples: List[int]) -> bytes:
    """Encodes 16-bit raw 3-axis accelerometer counts."""
    assert len(x_samples) == len(y_samples) == len(z_samples)
    packed = bytearray()
    for x, y, z in zip(x_samples, y_samples, z_samples):
        packed.extend(struct.pack("<hhh", x, y, z))
    return bytes(packed)

def decode_adxl_payload(payload: bytes) -> Tuple[List[int], List[int], List[int]]:
    sample_count = len(payload) // 6
    x, y, z = [], [], []
    for i in range(sample_count):
        xi, yi, zi = struct.unpack_from("<hhh", payload, i * 6)
        x.append(xi)
        y.append(yi)
        z.append(zi)
    return x, y, z

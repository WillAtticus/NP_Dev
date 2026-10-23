import os
import sys

# Ensure shared directory is importable
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from shared.schemas.protocol import (
    NeuroPulsePacket,
    MSG_TYPE_DATA_PIEZO,
    MSG_TYPE_DATA_ADXL,
    encode_piezo_payload,
    decode_piezo_payload,
    encode_adxl_payload,
    decode_adxl_payload,
    compute_crc16_ccitt,
)
from backend.app.services.acquisition.manager import AcquisitionManager

def test_piezo_packet_roundtrip():
    samples = [2048, 2100, 1950, 2040, 2060]
    payload = encode_piezo_payload(samples)
    packet = NeuroPulsePacket(
        msg_type=MSG_TYPE_DATA_PIEZO,
        seq_num=42,
        timestamp_us=12345678,
        payload=payload
    )
    encoded = packet.encode()
    decoded, err = NeuroPulsePacket.decode(encoded)

    assert err is None
    assert decoded is not None
    assert decoded.msg_type == MSG_TYPE_DATA_PIEZO
    assert decoded.seq_num == 42
    assert decoded.timestamp_us == 12345678
    assert decoded.payload == payload

    recovered_samples = decode_piezo_payload(decoded.payload)
    assert recovered_samples == samples

def test_adxl_packet_roundtrip():
    x = [10, -5, 20]
    y = [0, 15, -30]
    z = [256, 250, 260]
    payload = encode_adxl_payload(x, y, z)
    packet = NeuroPulsePacket(
        msg_type=MSG_TYPE_DATA_ADXL,
        seq_num=101,
        timestamp_us=87654321,
        payload=payload
    )
    encoded = packet.encode()
    decoded, err = NeuroPulsePacket.decode(encoded)

    assert err is None
    assert decoded is not None
    assert decoded.msg_type == MSG_TYPE_DATA_ADXL
    assert decoded.seq_num == 101

    rx, ry, rz = decode_adxl_payload(decoded.payload)
    assert rx == x
    assert ry == y
    assert rz == z

def test_corrupted_crc_detection():
    packet = NeuroPulsePacket(
        msg_type=MSG_TYPE_DATA_PIEZO,
        seq_num=1,
        timestamp_us=1000,
        payload=b"\x01\x02"
    )
    encoded = bytearray(packet.encode())
    # Corrupt last byte of CRC
    encoded[-1] ^= 0xFF
    decoded, err = NeuroPulsePacket.decode(bytes(encoded))

    assert decoded is None
    assert "CRC mismatch" in err


def test_duplicate_and_stale_data_packets_are_rejected_before_storage():
    manager = AcquisitionManager(data_root=".")
    manager.is_simulated = False
    manager.selected_sensor = "PIEZO_LDT0_028K"
    manager._ingest_packet(NeuroPulsePacket(
        msg_type=MSG_TYPE_DATA_PIEZO, seq_num=7, timestamp_us=1_000_000,
        payload=encode_piezo_payload([2048, 2050]),
    ))
    manager._ingest_packet(NeuroPulsePacket(
        msg_type=MSG_TYPE_DATA_PIEZO, seq_num=7, timestamp_us=1_002_000,
        payload=encode_piezo_payload([2049, 2051]),
    ))
    manager._ingest_packet(NeuroPulsePacket(
        msg_type=MSG_TYPE_DATA_PIEZO, seq_num=6, timestamp_us=1_003_000,
        payload=encode_piezo_payload([2047, 2052]),
    ))

    assert manager.total_packets_received == 1
    assert manager.total_samples_received == 2
    assert list(manager.live_channels["raw_counts"]) == [2048.0, 2050.0]
    assert manager.malformed_packets == 2

if __name__ == "__main__":
    test_piezo_packet_roundtrip()
    test_adxl_packet_roundtrip()
    test_corrupted_crc_detection()
    print("[+] All protocol unit tests passed successfully!")

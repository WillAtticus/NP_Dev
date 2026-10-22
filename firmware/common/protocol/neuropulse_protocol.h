#ifndef NEUROPULSE_PROTOCOL_H
#define NEUROPULSE_PROTOCOL_H

#include <stdint.h>
#include <stddef.h>

#ifdef __cplusplus
extern "C" {
#endif

#define NP_SYNC_BYTE_1 0xAA
#define NP_SYNC_BYTE_2 0x55
#define NP_PROTOCOL_VERSION 0x01

// Message types
#define NP_MSG_HELLO       0x01
#define NP_MSG_DATA_PIEZO  0x02
#define NP_MSG_DATA_ADXL   0x03
#define NP_MSG_ACK         0x0A
#define NP_MSG_ERROR       0x0E
#define NP_MSG_STATUS      0x0F

#pragma pack(push, 1)
typedef struct {
    uint8_t  sync1;
    uint8_t  sync2;
    uint8_t  msg_type;
    uint8_t  proto_ver;
    uint16_t payload_len;
    uint32_t seq_num;
    uint64_t timestamp_us;
} NeuroPulseHeader;
#pragma pack(pop)

static inline uint16_t np_compute_crc16(const uint8_t *data, size_t len) {
    uint16_t crc = 0xFFFF;
    for (size_t i = 0; i < len; i++) {
        crc ^= ((uint16_t)data[i] << 8);
        for (uint8_t bit = 0; bit < 8; bit++) {
            if (crc & 0x8000) {
                crc = (crc << 1) ^ 0x1021;
            } else {
                crc = (crc << 1);
            }
        }
    }
    return crc;
}

#ifdef __cplusplus
}
#endif

#endif // NEUROPULSE_PROTOCOL_H

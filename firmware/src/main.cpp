#include <Arduino.h>
#include "neuropulse_protocol.h"
#include "device_info.h"
#include "drivers/piezo_adc/piezo_driver.h"
#include "drivers/adxl345/adxl345_driver.h"

// Global state
static PiezoDriver piezoDriver(34);
static ADXL345Driver adxlDriver(0x53);
static SensorDriver *activeDriver = &piezoDriver;

static bool isStreaming = false;
static uint32_t sequenceNumber = 0;
static uint32_t targetSampleRateHz = 1000;
static uint32_t sampleIntervalUs = 1000; // 1000 us = 1ms for 1000Hz
static uint64_t lastSampleTimeUs = 0;

void sendPacket(uint8_t msgType, const uint8_t *payload, uint16_t len) {
    NeuroPulseHeader header;
    header.sync1 = NP_SYNC_BYTE_1;
    header.sync2 = NP_SYNC_BYTE_2;
    header.msg_type = msgType;
    header.proto_ver = NP_PROTOCOL_VERSION;
    header.payload_len = len;
    header.seq_num = sequenceNumber++;
    header.timestamp_us = esp_timer_get_time();

    uint8_t buffer[sizeof(NeuroPulseHeader) + len + 2];
    memcpy(buffer, &header, sizeof(NeuroPulseHeader));
    if (len > 0 && payload != nullptr) {
        memcpy(buffer + sizeof(NeuroPulseHeader), payload, len);
    }
    uint16_t crc = np_compute_crc16(buffer, sizeof(NeuroPulseHeader) + len);
    memcpy(buffer + sizeof(NeuroPulseHeader) + len, &crc, 2);

    Serial.write(buffer, sizeof(buffer));
}

void processCommand(const String &cmd) {
    String trimmed = cmd;
    trimmed.trim();

    if (trimmed == "HELLO" || trimmed == "GET_INFO") {
        String info = String("{\"device_id\":\"") + NP_DEVICE_ID + 
                      "\",\"firmware_version\":\"" + NP_FIRMWARE_VER + 
                      "\",\"hardware_rev\":\"" + NP_HARDWARE_REV + 
                      "\",\"sensor_type\":\"" + ((activeDriver->getModality() == SENSOR_PIEZO) ? "PIEZO_LDT0_028K" : "ADXL345") + 
                      "\"}";
        sendPacket(NP_MSG_HELLO, (const uint8_t*)info.c_str(), info.length());
    } 
    else if (trimmed == "GET_STATUS") {
        String status = String("{\"streaming\":") + (isStreaming ? "true" : "false") + 
                        ",\"seq\":" + sequenceNumber + 
                        ",\"sample_rate\":" + targetSampleRateHz + "}";
        sendPacket(NP_MSG_STATUS, (const uint8_t*)status.c_str(), status.length());
    }
    else if (trimmed.startsWith("SELECT_SENSOR")) {
        if (trimmed.indexOf("ADXL") >= 0) {
            activeDriver = &adxlDriver;
            targetSampleRateHz = 100;
        } else {
            activeDriver = &piezoDriver;
            targetSampleRateHz = 1000;
        }
        const bool sensorReady = activeDriver->begin();
        sampleIntervalUs = 1000000 / targetSampleRateHz;
        const bool rateConfigured = sensorReady && activeDriver->configure(targetSampleRateHz);
        if (rateConfigured) {
            sendPacket(NP_MSG_ACK, (const uint8_t*)"OK", 2);
        } else {
            const char *error = "SENSOR_INIT_FAILED";
            sendPacket(NP_MSG_ERROR, (const uint8_t*)error, strlen(error));
        }
    }
    else if (trimmed.startsWith("CONFIGURE")) {
        // CONFIGURE <hz>
        int spaceIdx = trimmed.indexOf(' ');
        if (spaceIdx > 0) {
            uint32_t rate = trimmed.substring(spaceIdx + 1).toInt();
            if (rate > 0 && rate <= 2000) {
                targetSampleRateHz = rate;
                sampleIntervalUs = 1000000 / targetSampleRateHz;
                activeDriver->configure(targetSampleRateHz);
            }
        }
        sendPacket(NP_MSG_ACK, (const uint8_t*)"OK", 2);
    }
    else if (trimmed == "START_STREAM") {
        isStreaming = true;
        sequenceNumber = 0;
        lastSampleTimeUs = esp_timer_get_time();
        sendPacket(NP_MSG_ACK, (const uint8_t*)"STREAMING_STARTED", 17);
    }
    else if (trimmed == "STOP_STREAM") {
        isStreaming = false;
        sendPacket(NP_MSG_ACK, (const uint8_t*)"STREAMING_STOPPED", 17);
    }
    else if (trimmed == "PING") {
        sendPacket(NP_MSG_ACK, (const uint8_t*)"PONG", 4);
    }
}

void setup() {
    Serial.begin(115200);
    while (!Serial) {
        delay(10);
    }
    activeDriver->begin();
}

void loop() {
    // Read host commands
    if (Serial.available()) {
        String cmd = Serial.readStringUntil('\n');
        processCommand(cmd);
    }

    // Stream samples if enabled
    if (isStreaming) {
        uint64_t now = esp_timer_get_time();
        if (now - lastSampleTimeUs >= sampleIntervalUs) {
            lastSampleTimeUs = now;
            uint8_t sampleBuf[16];
            size_t bytesRead = activeDriver->readSamples(sampleBuf, sizeof(sampleBuf));
            if (bytesRead > 0) {
                sendPacket(activeDriver->getMsgType(), sampleBuf, bytesRead);
            }
        }
    }
}

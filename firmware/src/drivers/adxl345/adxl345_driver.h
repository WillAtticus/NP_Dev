#ifndef ADXL345_DRIVER_H
#define ADXL345_DRIVER_H

#include <Arduino.h>
#include <Wire.h>
#include "sensor_driver.h"
#include "neuropulse_protocol.h"

// ADXL345 Registers
#define ADXL345_ADDR        0x53
#define ADXL345_REG_DATAX0  0x32
#define ADXL345_REG_POWER_CTL 0x2D
#define ADXL345_REG_DATA_FORMAT 0x31
#define ADXL345_REG_BW_RATE 0x2C

class ADXL345Driver : public SensorDriver {
private:
    uint8_t m_i2cAddr;
    uint32_t m_sampleRateHz;

public:
    explicit ADXL345Driver(uint8_t i2cAddr = ADXL345_ADDR) 
        : m_i2cAddr(i2cAddr), m_sampleRateHz(100) {}

    bool begin() override {
        Wire.begin();
        // Standby mode to configure
        Wire.beginTransmission(m_i2cAddr);
        Wire.write(ADXL345_REG_POWER_CTL);
        Wire.write(0x00);
        if (Wire.endTransmission() != 0) return false;

        // Data format: +/- 2g, full resolution
        Wire.beginTransmission(m_i2cAddr);
        Wire.write(ADXL345_REG_DATA_FORMAT);
        Wire.write(0x08);
        Wire.endTransmission();

        // Measurement mode
        Wire.beginTransmission(m_i2cAddr);
        Wire.write(ADXL345_REG_POWER_CTL);
        Wire.write(0x08);
        Wire.endTransmission();
        return true;
    }

    bool configure(uint32_t sampleRateHz) override {
        m_sampleRateHz = sampleRateHz;
        // Set BW_RATE: 100 Hz -> 0x0A, 200 Hz -> 0x0B
        uint8_t bw = (sampleRateHz >= 200) ? 0x0B : 0x0A;
        Wire.beginTransmission(m_i2cAddr);
        Wire.write(ADXL345_REG_BW_RATE);
        Wire.write(bw);
        return (Wire.endTransmission() == 0);
    }

    size_t readSamples(uint8_t *buffer, size_t maxLen) override {
        if (maxLen < 6) return 0;
        Wire.beginTransmission(m_i2cAddr);
        Wire.write(ADXL345_REG_DATAX0);
        if (Wire.endTransmission(false) != 0) return 0;

        Wire.requestFrom(m_i2cAddr, (uint8_t)6);
        if (Wire.available() < 6) return 0;

        for (int i = 0; i < 6; i++) {
            buffer[i] = Wire.read();
        }
        return 6;
    }

    SensorModality getModality() const override {
        return SENSOR_ADXL345;
    }

    uint8_t getMsgType() const override {
        return NP_MSG_DATA_ADXL;
    }
};

#endif // ADXL345_DRIVER_H

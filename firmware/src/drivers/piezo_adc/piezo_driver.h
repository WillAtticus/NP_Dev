#ifndef PIEZO_DRIVER_H
#define PIEZO_DRIVER_H

#include <Arduino.h>
#include "sensor_driver.h"
#include "neuropulse_protocol.h"

class PiezoDriver : public SensorDriver {
private:
    uint8_t m_pin;
    uint32_t m_sampleRateHz;

public:
    explicit PiezoDriver(uint8_t adcPin = 34) : m_pin(adcPin), m_sampleRateHz(1000) {}

    bool begin() override {
        analogReadResolution(12);
        analogSetAttenuation(ADC_11db);
        pinMode(m_pin, INPUT);
        return true;
    }

    bool configure(uint32_t sampleRateHz) override {
        m_sampleRateHz = sampleRateHz;
        return true;
    }

    size_t readSamples(uint8_t *buffer, size_t maxLen) override {
        if (maxLen < sizeof(uint16_t)) return 0;
        uint16_t val = (uint16_t)analogRead(m_pin);
        memcpy(buffer, &val, sizeof(uint16_t));
        return sizeof(uint16_t);
    }

    SensorModality getModality() const override {
        return SENSOR_PIEZO;
    }

    uint8_t getMsgType() const override {
        return NP_MSG_DATA_PIEZO;
    }
};

#endif // PIEZO_DRIVER_H

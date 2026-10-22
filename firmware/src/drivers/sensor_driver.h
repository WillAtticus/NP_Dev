#ifndef SENSOR_DRIVER_H
#define SENSOR_DRIVER_H

#include <stdint.h>
#include <stddef.h>
#include "device_info.h"

class SensorDriver {
public:
    virtual ~SensorDriver() = default;
    virtual bool begin() = 0;
    virtual bool configure(uint32_t sampleRateHz) = 0;
    virtual size_t readSamples(uint8_t *buffer, size_t maxLen) = 0;
    virtual SensorModality getModality() const = 0;
    virtual uint8_t getMsgType() const = 0;
};

#endif // SENSOR_DRIVER_H

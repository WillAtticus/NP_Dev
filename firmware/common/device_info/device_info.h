#ifndef DEVICE_INFO_H
#define DEVICE_INFO_H

#define NP_DEVICE_ID "NP-ESP32-DEV01"
#define NP_FIRMWARE_VER "0.1.0"
#define NP_HARDWARE_REV "ESP32-WROOM-32"

enum SensorModality {
    SENSOR_PIEZO = 1,
    SENSOR_ADXL345 = 2,
    SENSOR_NONE = 0
};

#endif // DEVICE_INFO_H

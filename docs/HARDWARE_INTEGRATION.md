# Hardware Integration Guide — NeuroPulse MVP

---

## 1. Hardware Branches

NeuroPulse supports two experimental hardware configurations:

### Branch A: Piezoelectric Film (LDT0-028K)
- **Sensor:** LDT0-028K Piezo Film with mass/strain fixation on the wrist.
- **Analog Front-End:** LM358 operational amplifier with DC offset biasing (e.g. $V_{cc}/2 \approx 1.65\text{V}$) and gain tuning.
- **MCU ADC:** ESP32 ADC1 (e.g., GPIO 34 / 36), 12-bit resolution (0–4095 counts).
- **Target Rate:** 1000 Hz via hardware timer interrupt.
- **Cost Estimate:** ~429,000 VND.

### Branch B: Digital 3-Axis Accelerometer (ADXL345)
- **Sensor:** ADXL345 digital 3-axis accelerometer.
- **Interface:** I2C (SDA: GPIO 21, SCL: GPIO 22) or SPI.
- **Dynamic Range:** Configurable $\pm 2g$, $\pm 4g$, $\pm 8g$, $\pm 16g$.
- **Output Data Rate (ODR):** Configurable 100 Hz, 200 Hz, 400 Hz.
- **Cost Estimate:** ~214,000 VND (Cost-optimized branch).

---

## 2. Hardware-In-The-Loop (HIL) Checklist

- [ ] Verify ADC input voltage never exceeds ESP32 absolute maximum (3.3V).
- [ ] Measure effective ADC linearity and noise floor with grounded / disconnected sensor.
- [ ] Verify ADXL345 I2C device ID `0xE5` readback.
- [ ] Measure USB serial throughput and packet loss over 5-minute continuous streaming session.
- [ ] Test graceful reconnection when USB cable is physically unplugged and replugged.

## 3. Current Host/Firmware Integration Readiness

- The host requests `SELECT_SENSOR` when opening a physical serial port and discards non-data control frames. Only matching Piezo or ADXL345 data message types are forwarded to the sensor adapter.
- Payload alignment is checked before decoding; malformed sample payloads are counted separately from CRC failures.
- Current firmware serial baud is fixed at 115200; use that value until a negotiated/configurable baud implementation is verified on both ends.
- The current firmware acquisition loop has not been measured on hardware. Piezo 1000 Hz and ADXL345 ODR remain targets/configuration claims until sample timestamps and loss/jitter are validated by HIL.
- HIL remains blocked on access to the physical board/sensors, circuit safety checks, and operator verification of the actual wiring and calibration.

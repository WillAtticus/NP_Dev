# Signal Processing Profiles Specification — NeuroPulse MVP

---

## 1. Processing Profile Concept

Signal processing in NeuroPulse is fully configurable through versioned profiles. Different sensors (Piezo vs. ADXL345) and experimental protocols use distinct profiles without altering core engine logic.

---

## 2. Standard Profiles

### Profile: `piezo_butterworth_1_20_default`
- **Sensor Type:** `PIEZO_LDT0_028K`
- **Sampling Rate Target:** 1000 Hz
- **Detrending:** Constant / Linear mean subtraction
- **Bandpass Filter:** Butterworth IIR, Order 4, Passband 1.0 Hz – 20.0 Hz
- **Notch Filter:** Optional 50 Hz notch (Q=30)
- **Window Length:** 8.0 seconds (8000 samples)
- **Window Overlap:** 50% (4.0 seconds)
- **Spectral Method:** Welch PSD (Hann window, segment length = 4s, 50% overlap)
- **Bands Defined:**
  - Micro-tremor target band: `[3.0, 6.0]` Hz
  - Denominator reference band: `[1.0, 20.0]` Hz

### Profile: `piezo_butterworth_5_20_candidate`
- **Sensor Type:** `PIEZO_LDT0_028K`
- **Bandpass Filter:** Butterworth IIR, Order 4, Passband 5.0 Hz – 20.0 Hz
- **Bands Defined:**
  - Micro-tremor target band: `[3.0, 6.0]` Hz
  - Denominator reference band: `[5.0, 20.0]` Hz

### Profile: `adxl345_triaxial_100hz`
- **Sensor Type:** `ADXL345`
- **Sampling Rate Target:** 100 Hz (or 200 Hz)
- **Channels:** `["x", "y", "z"]` + optional derived vector magnitude `mag = sqrt(x^2 + y^2 + z^2)`
- **Gravity Removal:** Highpass filter 0.5 Hz or DC mean subtraction
- **Bandpass Filter:** Butterworth IIR, Order 4, Passband 1.0 Hz – 20.0 Hz
- **Window Length:** 8.0 seconds (800 samples)

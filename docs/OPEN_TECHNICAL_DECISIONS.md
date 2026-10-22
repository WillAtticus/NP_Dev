# Open Technical Decisions & Decision Log (NeuroPulse MVP)

This document tracks technical decisions, unknowns, hardware parameters, and contradictions identified across project documents.

---

## 1. Decision Status Summary

| ID | Title / Question | Safe MVP Default | Resolution Condition | Current Status |
|---|---|---|---|---|
| **D-001** | Exact ESP32 board variant | Abstract board capabilities; support standard ESP32-WROOM-32 / DevKit v1 | Confirm upon physical board arrival | Open |
| **D-002** | Firmware framework | PlatformIO with Arduino-ESP32 / ESP-IDF core | Verify build reproducibility on real board | Open |
| **D-003** | Piezo analog front-end gain, bias & ADC calibration | Store raw ADC counts (12-bit, 0–4095); voltage mapping optional via calibration config | Measure physical circuit response | Open |
| **D-004** | Piezo sampling rate stability | Target: 1000 Hz; firmware records monotonic timestamps and measures actual rate | HIL test with hardware timer | Open |
| **D-005** | ADXL345 ODR & dynamic range | Configurable (Default: ±2g or ±4g, ODR 100 Hz / 200 Hz); do not force 1000 Hz | Check I2C/SPI throughput and research protocol | Open |
| **D-006** | Serial baud rate & packet batch size | Current firmware/UI use 115,200 baud and emit one sensor sample per data frame; this cannot carry the Piezo 1000 Hz target. Do not choose a remedy in software | Hardware team owns selection of batching/timestamp reconstruction or supported higher baud; then HIL throughput, loss, jitter, and timestamp validation | Open — deferred to hardware team (2026-10-21) |
| **D-007** | Binary framing protocol | Binary framing: Header `0xAA 0x55` + Length + Sequence + Timestamp + Payload + CRC16-CCITT | Parser & roundtrip unit tests passed | Proposed |
| **D-008** | Filter passband: 1–20 Hz vs 5–20 Hz | Provide configurable profiles (`piezo_butterworth_1_20` and `piezo_butterworth_5_20`) | Research team & clinical advisor review | Open |
| **D-009** | NPI mapping formula from TBR | `NPI_v1_baseline`: `100 * [1 - clip((TBR - 0.40) / (0.85 - 0.40), 0, 1)]` | Team approval received 2026-10-21 for experimental use; not clinical validation | Resolved (Experimental formula approved) |
| **D-010** | TBR thresholds (0.40 & 0.85) role | Initial experimental reference constants; configurable in Algorithm Lab | Clinical validation dataset | Open (Configurable) |
| **D-011** | Welch PSD window, overlap & scaling | Configurable (Default: 8s window, Hann, 50% overlap, `density` scaling) | Validate against synthetic multi-tone signal | Open |
| **D-012** | ADXL345 multi-axis analysis | Analyze X, Y, Z independently; provide optional derived vector magnitude | Research protocol specification | Open |
| **D-013** | Raw storage format: HDF5 vs NPZ | HDF5 (`h5py`) with fallback to chunked NPZ | Storage throughput benchmark | Proposed (HDF5) |
| **D-014** | Prototype access model | No sign-in on the local Windows prototype; staff selects an operation mode on the local machine and patients use a patient code for personal lookup | Implement real identity/access controls before any shared, networked, or clinical deployment | Resolved for current prototype only (mode selection is not authentication) |
| **D-015** | Patient view and screening demo | Patient can view own measures, live results/charts, history, personal clinical information, and experimental threshold alerts | Advisor review and clinical validation before clinical interpretation | Prototype scope approved; thresholds remain experimental |
| **D-016** | Target host OS | Windows 10/11 primary, cross-platform backend (Linux/macOS compatible) | Host environment verified | Resolved (Windows first) |
| **D-017** | Meaning of NPI display bands at 40 and 70 | For prototype demo only: `>=70` reference range, `40–69` monitoring, `<40` outside reference range, based on prior handoff; label as experimental hypothesis | Advisor review and clinical validation before clinical interpretation | Approved for demo by team on 2026-10-21; not clinically validated |
| **D-018** | Local account password and session policy | Sign-in is removed from the current local prototype at the team's request; operation modes are UI/workflow restrictions only | Revisit identity, authentication, session expiry and account recovery before any shared, networked, or clinical deployment | Deferred / superseded for current prototype (2026-10-22) |
| **D-019** | Login throttling, backup protection, and audit tamper evidence | Accounts/authentication are local and loopback-only; backup archive has per-file checksums; audit records capture important actions | Approve lockout/rate-limit behavior, encryption-at-rest, backup retention, and tamper-evidence needs during workstation security review | Open |
| **D-020** | Patient code format | `N` + chromosome marker (`X`=XX, `Y`=XY) + age band + first-measurement year (2 digits) + random digits (5 digits, 00001–99999); remove birth year | Define mapping for unknown/other karyotype, century handling, and whether year means profile issuance or first actual measurement | Mostly implemented; code generator checks collisions. Current implementation uses profile creation year; actual first-measurement timing remains unresolved |
| **D-021** | Prototype retention | Keep patient/raw/clinical/result/history data for 3 weeks by default; Admin may enable indefinite research retention | Define expiry cleanup behavior and whether consent/audit metadata are retained after deletion | Profile expiry timestamp and Admin toggle implemented; automatic cleanup remains open |
| **D-022** | Prototype deployment scope | One local Windows 10/11 machine; no cross-machine sync or commercial deployment in initial prototype | Revisit if pilot or market deployment begins | Resolved for prototype |
| **D-023** | Patient code chromosome cases | Accept `X`=XX and `Y`=XY according to current group encoding | Define how unknown or other karyotype values are represented; current profile creation only accepts X/XX or Y/XY | Open |
| **D-024** | Windows desktop packaging and backend runtime | Use Electron window with local React assets and loopback FastAPI; no external browser | Bundle and verify Python backend/runtime, installer, data path, upgrade and uninstall behavior on clean Windows 10/11 machines | Desktop source shell implemented; standalone installer/runtime bundle remains open |
| **D-025** | Simulator scenario definitions and cohort summaries | Offer named `healthy` reference-shape and `volatile` higher 3–6 Hz energy scenarios; store scenario/provenance with each recording. Analytics are descriptive aggregates of local SQLite participant/session rows | Research team reviews synthetic parameter values and cohort metrics before using them in demonstrations or study planning | Implemented for software demo; synthetic values are provisional and not clinically calibrated |
| **D-026** | Patient self-measurement workspace | Patient mode is the default self-measurement workspace; selected code scopes new sessions, live waveform, results, and history. Patient UI excludes system statistics and research/technical detail | Verify complete profile-to-measurement flow and per-code isolation on desktop with simulator and both sensor profiles | Implemented in React/API; desktop workflow and two-profile isolation verification remain open |

---

## 2. In-Depth Analysis of Document Discrepancies

### D-006: Current Piezo serial throughput does not meet the 1000 Hz target
- Current wire frame overhead is 20 bytes (18-byte header + 2-byte CRC); one Piezo sample adds 2 bytes, for 22 bytes/sample.
- At the documented 1000 samples/s target, the stream requires about 22,000 bytes/s. 115,200 baud with 8N1 can carry at most 11,520 bytes/s, before USB/command overhead; therefore the current one-sample-per-frame implementation cannot meet that target.
- This is an open release-blocking interface decision. Choose batching/timestamp reconstruction or a supported higher baud and then verify sustained transfer, sample timing/jitter, and loss on the final HIL setup. Do not present the configured target rate as measured effective throughput.
- Team direction on 2026-10-21: defer the remedy choice to the hardware team. No batching size, timestamp reconstruction model, or higher baud rate is approved yet.

### D-008 & Specification Contradictions: Filter Bandwidth
- **Observation:** In the document summaries, the bandpass filter is cited as 5–20 Hz. In the detailed processing pipeline table, it is described as Butterworth 1–20 Hz.
- **Architectural Solution:** Never hard-code the filter cutoff frequencies. The processing pipeline loads filter parameters from a versioned `ProcessingProfile` JSON object. Both profiles (`1-20 Hz` and `5-20 Hz`) are supported and selectable in the Algorithm Lab.

### D-009: Experimental NPI Formula Approved
- **Status:** Resolved for experimental research use by explicit team confirmation on 2026-10-21. This updates the previous `FORMULA_PENDING` note in the master spec and supersedes the earlier document conflict.
- **Approved equation:**
  $$\text{TBR} = \frac{P_{3-6\text{ Hz}}}{P_{1-20\text{ Hz}}}$$
  $$\text{NPI} = 100 \times \left[ 1 - \text{clip}\left(\frac{\text{TBR} - 0.40}{0.85 - 0.40}, 0, 1\right) \right]$$
- `tbr_min=0.40` and `tbr_max=0.85` are approved formula parameters for the experimental version. Store the exact parameter snapshot with each result.
- Team has requested these bands for a prototype screening demo: `>=70` reference range, `40–69` monitoring, `<40` outside reference range, carried forward from the previous handoff. This is an experimental hypothesis, not a clinically validated threshold.
- The prototype may show an alert based on these bands, with explicit experimental status. Do not present the alert as a diagnosis, probability of disease, or validated clinical risk.

### Hardware Cost & Sensor Comparison
- **Piezo Prototype:** ~429,000 VND (LDT0-028K + LM358 + ESP32)
- **ADXL345 Cost-Optimized Prototype:** ~214,000 VND (ADXL345 + ESP32)
- **Handling:** Software treats both as independent sensor modalities with specialized adapters.

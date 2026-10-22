# NeuroPulse — Developer Context Handoff
> **Maintained during development** | Last updated: 2026-10-22T00:45 +07:00
> **Purpose:** Enable seamless handoff to another AI agent or developer. Read this entire file before writing any code.

---

## 🗺️ Project Location
- **Root:** `C:\Users\Thinkpad\Desktop\NeuroPulse\`
- **Spec (source of truth):** `Idea Hub\NEUROPULSE_ANTIGRAVITY_MVP_MASTER_SPEC.md` (1460 lines at 2026-10-22)
- **This file:** `Idea Hub\context_dev\HANDOFF.md`

---

## 🏗️ Architecture Overview

### Current product snapshot — 2026-10-22 (supersedes older UI/launch summaries below)

- **Default app:** `scripts/start.ps1` launches `desktop/package.json` → Electron + bundled React/Vite UI. Electron starts a local FastAPI process; SQLite and session files stay on this workstation. Streamlit is a separate development/diagnostic path (`scripts/run_streamlit.ps1`), not the default desktop app.
- **Default mode:** Patient. The root route is now the self-measurement workspace in `frontend/neuropulse-ui/src/pages/PatientMeasurementPage.tsx`; the older `PatientPortalPage.tsx` is still in source but is not routed. Patient export has not yet been added to the replacement screen.
- **Modes are not identity/security controls:** Sign-in was removed at the user's request. Staff modes and patient-code checks scope local workflows only. Do not claim production access control or multi-user privacy.
- **Latest verified change:** React desktop bundle built and copied into `desktop/ui`; Python syntax compile and FastAPI import/OpenAPI generation succeeded. A full Electron-to-loopback workflow, visual review, hardware/HIL and latest patient isolation checks remain unverified.
- **Current gap ledger:** See `context_dev\drift-away.md` for deviations from the original description, tested evidence, and prioritized gaps.

```
Sensor (Piezo LDT0-028K / ADXL345) → ESP32 Firmware → USB Serial (115200 baud; current firmware emits one sample per data frame)
  → Python AcquisitionManager (binary framing 0xAA55 + CRC16-CCITT)
  → FastAPI Backend (local port 8000) ↔ React/Vite UI in Electron window
  → Signal Processing Engine (Butterworth IIR → Welch PSD → TBR → experimental NPI)
  → SQLite DB (sessions, patients, devices, studies, audit logs) + HDF5 / JSON (raw sample arrays)
```

### Tech Stack
- **Firmware:** C++ / PlatformIO / Arduino-ESP32
- **Backend:** Python 3.14 / FastAPI / Pydantic v2 / SQLAlchemy 2.0 / SQLite
- **Signal Processing:** NumPy / SciPy (Butterworth IIR, Welch PSD, trapezoid integration)
- **Raw Storage:** HDF5 (`h5py` gzip chunked compression) + JSON fallback with SHA-256 integrity
- **Default desktop UI:** Electron + React 18 + Vite + TypeScript (bundled local UI)
- **Separate diagnostic UI:** Streamlit (`scripts/run_streamlit.ps1`, port 8501); not the default desktop launch path
- **Testing:** pytest (37 tests passing in latest full-suite run)

## Latest Product Direction Update — 2026-10-21
- Initial target is an internal Windows 10/11 prototype for KHKT/science fair demos and fundraising; local-only on one machine. Multi-machine sync/commercial rollout are deferred.
- Support both Piezo and ADXL345 so the team can compare sensor configurations.
- Include patient and staff screens. Patient enters a patient code to open their own profile; staff selects a local operation mode. Modes are UI/action restrictions, not authentication. Admin, Researcher, Operator, and Clinical Reviewer have broad dataset access in the prototype; Operator has research-level viewing. Patient can view/export only their own personal data. No separate hospital account system is needed now.
- Current patient code proposal: `N` + chromosome (`X`=XX, `Y`=XY) + age band + two-digit year of first measurement + five random digits (`00001–99999`); birth-year digits removed. Must collision-check. The `Y` code is also an age-band symbol for under 30, so parsing must use fixed positions. Handling for unknown/other karyotypes, century interpretation, and uniqueness scope remains open.
- Retain patient profile, clinical information, continuous/raw data, results, and history for 3 weeks by default. Admin can enable indefinite research retention. Profile expiry timestamps and Admin toggle are implemented; automatic cleanup of profiles/sessions/raw files remains open.
- Team wants working demo alerts based on the existing hypothesis rather than placeholders. Earlier handoff specifies NPI `>=70` reference range, `40–69` monitoring, `<40` outside reference range. Current team direction authorizes these bands for an explicitly experimental prototype demo; they are not clinically validated and must not be represented as validated risk probabilities/diagnoses. Master spec section 9.2 and D-017 have been updated to record this change.
- Real participant measurement is planned after the team obtains an advisor, participant permission, and applicable approvals/protocols.
- Screening-band implementation now exists in `backend/app/services/algorithms/npi.py`: valid NPI returns experimental category, alert level, and rule ID `NPI_DEMO_BANDS_40_70_v1`; invalid/insufficient results return no alert. Completed sessions persist `npi_category`; session exports include the category/rule marker. Streamlit live sensing displays the three experimental bands with explicit non-clinical language.
- Verification: `backend/tests/test_processing_and_npi.py` **18 passed** after the change. A combined run including `test_api.py` stalled after initial progress and was interrupted; no API-suite pass is claimed. `git diff --check` completed without whitespace errors.
- Implemented this continuation: `patients` table and Alembic revision `0002_patients`; code generation/age-band mapping with collision checks; staff profile creation/listing and Admin retention toggle; loopback-only patient-code lookup returning the personal profile and matching session history; React staff patient registry; patient portal at `/patient` with NPI band display and personal JSON export; Live Sensing requires an existing patient code before starting.
- Remaining: actual automatic 3-week purge (including session raw files); staff mode selector (existing account login/RBAC remains and conflicts with latest prototype mode-selection direction); patient live monitor integration; access-controlled patient export beyond local code lookup; patient profile edit/delete. Code's two-digit year currently comes from profile creation rather than the first actual measurement; decide whether the first-measurement flow should issue the code instead. Unknown/other karyotype is not supported by the current code generator.
- Verification for this continuation: `tests/test_patients.py`, `tests/test_migrations.py`, and `tests/test_processing_and_npi.py` **23 passed** using a workspace-local pytest temp directory. React production build passed (140 modules); frontend tests passed (2). `git diff --check` clean apart from line-ending notices. The earlier physical sensor-path changes remain unverified.

### Streamlit Startup Error, Patient Screens and Retention (2026-10-21)
- User reported a Streamlit `IndentationError: unexpected indent` at `frontend/streamlit_app.py:1107` while viewing `http://127.0.0.1:8501`. Fixed the extra indentation on the experimental NPI disclaimer.
- The active `scripts/start.ps1` launcher uses Streamlit as its UI, while the patient portal and staff registry previously existed only in the secondary React scaffold. Added a Streamlit patient entry from the local login screen, patient-code lookup, personal profile/history and JSON export, plus staff patient creation/listing and Admin retention toggle. Reviewer mode is read-only on the registry. Patient lookup remains loopback-only at the API.
- Added startup/hourly purge for expired profiles, their non-active sessions and linked raw files; active recordings are deferred until a later cleanup pass. Indefinite-retention profiles are excluded. Updated the privacy note to describe this behavior.
- Python syntax compilation and `git diff --check` passed. Full Streamlit/backend runtime launch could not be confirmed in this environment because its bundled Python lacks `streamlit` and `sqlalchemy`; the Windows Store `python.exe` alias is inaccessible. Install the project's requirements on the target PC before launching with `scripts/start.ps1`. No backend tests or browser checks were run in this continuation.
- Current UI task: run the local launcher on the target Windows machine and review patient lookup, profile creation, retention control and measurement workflow in the browser. Mode-based staff selection, patient live display, role-wide delete/export, UI end-to-end checks and physical HIL remain open.

### Windows Desktop App Direction (2026-10-21)
- Team redirected the app to run in its own Windows desktop window rather than asking users to open a browser/localhost page.
- Added `desktop/main.cjs`, a hardened Electron shell that serves only bundled local UI through `neuropulse://app`, disables Node integration in the renderer, enables sandbox/context isolation, blocks external navigation/popups, and starts/stops the local loopback FastAPI child process. Added desktop CORS origin and absolute local API base URL for this origin.
- Added `scripts/build_desktop.ps1`; `desktop/package.json` runs the React desktop build then Electron. `npm run build:ui` succeeded: 140 modules, 297.47 kB JS and 13.48 kB CSS. `node --check desktop/main.cjs` and `git diff --check` both passed.
- Repointed the standard `scripts/start.ps1` launcher to the desktop window; Streamlit launch scripts remain available for development diagnostics.
- Electron npm package install succeeded, but Electron's Windows runtime binary download failed (`fetch failed`) from the release host. The desktop window therefore could not be launched in this environment. The current shell expects Python and `backend/requirements.txt` locally. This is not yet a self-contained Windows installer; bundling the Python backend/runtime and installer remains D-024.
- README now documents the desktop developer workflow and retains the Streamlit app as a diagnostic/development interface. Do not call this commercial-ready, a standalone installer, or clinically validated.

---

## ✅ COMPLETED & VERIFIED (Current Status)

### 1. Database & Persistence Layer (`backend/app/db/`)
| Component | Status | Details |
|-----------|--------|---------|
| `database.py` | ✅ | SQLite engine (`neuropulse.db`), `SessionLocal`, `init_db()`, `get_db()` |
| `models.py` | ✅ | `Session`, `Device`, `Study`, `AuditEvent` models with soft deletion and full metadata |
| `crud.py` | ✅ | Full CRUD for Sessions, Devices, Studies, Audit Events, and aggregate stats |
| `schemas.py` | ✅ | Pydantic v2 models (`SessionCreate`, `SessionUpdate`, `SessionResponse`, `StudyCreate`, `StudyResponse`, `SessionStats`) |

### 2. Backend REST API (`backend/app/main.py`)
| Endpoint | Method | Tag | Description |
|----------|--------|-----|-------------|
| `/api/v1/health` | GET | System | Healthcheck & research disclaimer |
| `/api/v1/devices/ports` | GET | Device | Scan physical and virtual COM ports |
| `/api/v1/devices/connect` | POST | Device | Connect to COM port or virtual simulator |
| `/api/v1/devices/disconnect` | POST | Device | Disconnect serial stream |
| `/api/v1/devices/status` | GET | Device | Status, sample rate, CRC error counters |
| `/api/v1/acquisition/start` | POST | Acquisition | Start streaming & recording |
| `/api/v1/acquisition/stop` | POST | Acquisition | Stop streaming & write HDF5/JSON data |
| `/api/v1/acquisition/live-buffer` | GET | Acquisition | Polling buffer for live visualization |
| `/api/v1/studies` | GET | Studies | List research study protocol templates (seeds default if empty) |
| `/api/v1/studies` | POST | Studies | Create new research protocol template |
| `/api/v1/sessions` | POST | Sessions | Create session record + audit event |
| `/api/v1/sessions` | GET | Sessions | List sessions (provenance/status filters, pagination) |
| `/api/v1/sessions/stats/summary` | GET | Sessions | Aggregate statistics (total, completed, avg NPI) |
| `/api/v1/sessions/{id}` | GET | Sessions | Fetch single session by UUID |
| `/api/v1/sessions/{id}` | PATCH | Sessions | Update metrics (TBR, NPI, quality status) |
| `/api/v1/sessions/{id}` | DELETE | Sessions | Soft-delete session + audit log |
| `/api/v1/sessions/{id}/export` | GET | Sessions | Export session metadata & waveform array (JSON / CSV format) |
| `/api/v1/benchmark/import` | POST | Benchmark | Import benchmark dataset, compute metrics, persist HDF5 & DB |
| `/api/v1/processing/profiles` | GET | Processing | List built-in Butterworth filter profiles |
| `/api/v1/processing/analyse` | POST | Processing | Run pipeline on stored HDF5/JSON session |
| `/api/v1/simulate-and-analyse` | POST | Processing | One-shot synthetic signal generation & NPI |
| `/api/v1/algorithms` | GET | Algorithm Lab | List registered algorithms |
| `/api/v1/algorithms/npi/compute` | POST | Algorithm Lab | Compute NPI from TBR ratio |
| `/ws/live-stream` | WebSocket | Live | Real-time sample batch broadcast |

### 3. Signal Processing & Algorithms
- **Engine (`engine.py`):** Detrend → Butterworth IIR → Welch PSD → Band Power (3-6 Hz & 1-20 Hz) → Quality Gate.
- **NumPy 2.x compatibility:** Uses `getattr(np, 'trapezoid', np.trapz)` for spectral integration.
- **Quality Gate:** Flatline detection, ADC clipping saturation (0 / 4095), insufficient sample duration, sample rate mismatch.
- **NPI Formula:**
  $$\text{TBR} = \frac{P_{3-6\text{ Hz}}}{P_{1-20\text{ Hz}}}$$
  $$\text{NPI} = 100 \times \left[ 1 - \text{clip}\left(\frac{\text{TBR} - 0.40}{0.85 - 0.40}, 0, 1\right) \right]$$
  - Prototype demo bands per latest team direction: $\ge 70$ (experimental reference range), $40-69$ (experimental monitoring), $< 40$ (outside experimental reference range). Not clinically validated; do not present as a diagnosis or validated risk score.
  - Configurable parameters `tbr_min` / `tbr_max`.

### 4. Storage Architecture (STORE-01 & D-013)
- `AcquisitionManager._persist_session_data()` writes:
  - `raw.h5`: HDF5 format with gzip chunk compression, root metadata attributes, and channel datasets.
  - `raw.json`: JSON payload with SHA-256 integrity checksum for quick inspection.
- `analyse_session` endpoint directly reads `raw.h5` (with graceful fallback to `raw.json`).
- `export_session_endpoint` exports both JSON and CSV time-series data from `raw.h5`.

### 5. Legacy / diagnostic Streamlit Dashboard (`frontend/streamlit_app.py`)
- **7 Core IA Sections:**
  1. 🏠 **Overview / Home:** System status, backend auto-detect, recent sessions list, quick-start session.
  2. 📡 **Live Sensing:** Study protocol selection, participant pseudonym input (Zero-PHI), session lifecycle (`idle` → `configured` → `recording` → `stopped`), real computed metrics from engine, live Butterworth waveform, auto-save to backend DB on stop.
  3. 🔬 **Signal Lab:** Dual-tab analysis: Butterworth & Welch PSD inspection + NPI sensitivity curve calibration.
  4. 🧪 **Simulation & Test:** 6 preset test scenarios with prominent `🔶 MÔ PHỎNG` badges and `[MÔ PHỎNG]` chart headers.
  5. 📊 **Benchmark & Research:** Functional Benchmark Studio: upload CSV/JSON or load synthetic cohorts, run analysis via `/api/v1/benchmark/import`, view PSD and NPI.
  6. 📁 **Sessions & History:** Dynamically pulls sessions and stats from `/api/v1/sessions`, inspects JSON metadata, download JSON report & CSV raw time series.
  7. 🔌 **Devices & Profiles:** Dynamically queries available serial/virtual ports from `/api/v1/devices/ports`, inspects processing profile schemas.

### 6. Automated Test Suite
- **37 tests (`pytest backend/tests/ -q`)**:
  - `test_acquisition_hdf5.py`: HDF5 file generation, dataset attributes, and HDF5 analysis endpoint.
  - `test_export_and_benchmark.py`: Benchmark import endpoint, JSON export, and CSV time-series export.
  - `test_studies.py`: Study model seeding, listing, and creation.
  - `test_api.py`: Health, simulation, algorithm registry, and session CRUD API cycle.
  - `test_database.py`: SQLAlchemy session lifecycle, soft deletion, stats, audit events, devices, Pydantic schemas.
  - `test_processing_and_npi.py`: Band power, Welch PSD, quality gate flags, NPI formula edge cases, protocol CRC.
  - `test_protocol.py`: Binary packet encode/decode roundtrip, CRC-16 CCITT verification.

---

## 🚀 How to Launch the Application

### 1. Default Windows desktop launcher
- Run `scripts/start.ps1` from the project folder (or use a shortcut that targets this script, if installed on the target workstation).
- It calls `npm start` from `desktop/`, rebuilds the React UI through `scripts/build_desktop.ps1`, then opens the Electron app and its local FastAPI child process.
- This is a developer/local prototype launcher, not an installed standalone executable. It requires the workspace dependencies and local Python environment. No clean-machine installer verification is recorded.

### 2. Separate Streamlit diagnostic UI
```powershell
cd C:\Users\Thinkpad\Desktop\NeuroPulse
.\scripts\run_streamlit.ps1
```
This is not the default application path. The Electron app starts its own API process.

### 3. Run Verification Tests
```powershell
python -m pytest backend/tests/ -v --tb=short
```

---

## ❌ REMAINING WORK FOR FULL MATURITY (Priority Order)

### Milestone Gate Snapshot (M0 → M11)
| Milestone | Current evidence | Gate state |
|---|---|---|
| M0 Foundation | Monorepo, specs, docs, local run instructions, open-decision log | Substantially implemented; formal architecture/docs review and clean reproducible setup still needed |
| M1 Protocol/Firmware | Framing/parser tests and firmware source exist | Partial; reproducible PlatformIO firmware build/device status behavior not verified |
| M2 Dual sensor abstraction | Piezo/ADXL adapters and marked simulators exist | Software path present; physical sensor configuration/scaling unresolved |
| M3 Acquisition | Simulator-to-raw-file-to-session integration test passes | Simulator gate passes; physical throughput/recovery gates open |
| M4 Processing | Processing/NPI deterministic tests pass | Software tests pass; profiles/calibration and reference validation remain open |
| M5 Algorithm Lab | Experimental NPI formula and demo bands approved for prototype display, never as clinical claims | Formula/demo categories implemented; full persisted run/version snapshots remain incomplete |
| M6 Backend/Data | FastAPI + SQLite + local modes, patient records, session/export, migrations, audit and retention | Partial; sign-in intentionally removed for prototype; audit/per-run traceability/role export-delete parity need work |
| M7 Dashboard Core | Electron-hosted React default UI; Streamlit remains diagnostic/legacy | Partial; build passes, current patient workflow runtime/visual validation remains open |
| M8 Research workflows | React staff pages cover sessions, patient registry, benchmark/analysis, algorithm lab and cohort summaries; Kiosk is instruction-only | Partial; full protocol workflow, role-specific export/delete parity and persisted analysis-run provenance remain incomplete |
| M9 Integration readiness | Local docs and simulator tests | Not passed; stress, install reproducibility and protocol freeze evidence incomplete |
| M10 Hardware integration | Serial handshake and host parser logic | Not started on real hardware; HIL/circuit safety/calibration gates open |
| M11 MVP release | Backup/restore utility and documentation exist | Not passed; installer, backup policy, release report, and packaging remain incomplete |

Do not describe the current repository as commercial-ready or clinical-study-ready. Clinical research use additionally requires the applicable ethics/IRB approval, consent process, approved protocol, qualified supervision, and hardware safety verification.

### P1 — Research & Analytics Refinement
| ID | Item | Scope |
|----|------|-------|
| **WS-01** | Continuous Live UI Updates | The Streamlit view currently fetches the backend acquisition buffer during a page rerun. Add a supported refresh mechanism and consider `/ws/live-stream` only if it can be consumed safely by Streamlit. |
| **PDF-01** | PDF Research Report Generation | Export a reproducible research summary with provenance, configuration, processing/algorithm versions and quality warnings. |

### Recently Continued — Live Sensing Acquisition Wiring (2026-10-21)
- Live Sensing Start now calls `/api/v1/acquisition/start` with the active session ID and refuses to enter recording state if the backend reports no connected device/simulator.
- Stop now calls `/api/v1/acquisition/stop`; this lets the acquisition manager persist its raw recording.
- With the backend online, the chart and processing input come from `/api/v1/acquisition/live-buffer`. Synthetic fallback is used only when the backend is offline and is labeled `MÔ PHỎNG`.
- Connecting `SIMULATOR` through Devices & Profiles now calls the backend too, so simulator sessions use the same acquisition lifecycle.
- This gap was closed in the later “Acquisition-to-Session Full Lifecycle” section below; continuous refresh/WS-01 remains open.
- Initial verification was not run at this point; the later full-suite result below supersedes it.

### Acquisition-to-Session Full Lifecycle (2026-10-21)
- Live Sensing now sends session ID, sensor type, selected processing profile/channel, participant pseudonym, and study ID to acquisition start.
- Start validates sensor/profile pairing, refuses duplicate session IDs, creates the matching SQLite session with device/simulator provenance, start time, and a `session_started` audit event.
- Stop waits for the acquisition reader, persists raw HDF5/JSON, then links the same session to raw path, SHA-256, sample count/rate, end time, duration, and stopped audit event.
- Stop now runs the selected processing profile on the just-saved recording and records quality flags, TBR, dominant frequency, and experimental NPI. If analysis fails, raw data remains linked and immutable; session is closed with `ANALYSIS_FAILED` rather than left in `recording`.
- Session API response includes raw path and SHA-256 metadata for local research traceability.
- Added simulator end-to-end test for connect → start → stop → immutable file → finalized DB session linkage.
- At this stage `pytest backend/tests/ -q` passed **34 tests** (44 warnings); later authentication work brought the current full suite to 35 tests (62 warnings), recorded below.
- No physical hardware/HIL was available; no clinical study or deployment readiness is asserted.
- Follow-up consistency fix: removed unapproved NPI category presentation from the React scaffold and aligned privacy/database docs with D-017. The React scaffold has no installed Node dependencies in this checkout, so its build has not been verified; Streamlit remains the primary dashboard.

### Local Accounts and RBAC Foundation (2026-10-21)
- Team selected local accounts with roles (admin, operator, researcher, reviewer, kiosk); D-014 records this decision.
- First-run `/api/v1/auth/bootstrap` creates the initial admin; no default password exists. Passwords use stdlib scrypt and must be at least 12 characters.
- Opaque random bearer tokens are stored only as SHA-256 digests in `auth_sessions`; default expiry is 8 hours, configurable through `NEUROPULSE_SESSION_TTL_MINUTES` from 5 to 1440 minutes. Logout, account deactivation, and password reset revoke sessions.
- Admin can create accounts, disable/enable accounts, and reset passwords from the Streamlit sidebar. API role checks are server-side; reviewer is read-only, and kiosk navigation only presents procedural instructions.
- Authenticated REST and WebSocket calls are restricted to loopback. The Streamlit app sends bearer auth to protected endpoints; disconnected offline mode is synthetic-only.
- Auth/account and measurement lifecycle actions create audit events with the actor username.
- Removed pre-seeded mock session records; history now contains actual saved records only. Unauthenticated disconnected mode is limited to synthetic analysis and simulation pages.
- Security follow-up is open in D-018/D-019: approve password/session policy, login throttling, audit tamper evidence, retention, and workstation threat model before human research use. React/Vite local auth and acquisition/session workflows are now connected; production build succeeds, but browser/runtime review remains open.
- Verification at the authentication milestone: full backend suite passed **35 tests** (62 warnings); syntax compilation passed for backend auth/API/models and Streamlit. Backup tests and latest full-suite result are recorded below.

### Local Backup and Restore (2026-10-21)
- Added `scripts/neuropulse_backup.py` for SQLite-consistent snapshots plus local session raw files.
- Archives include a SHA-256 manifest and verify archived bytes before reporting success. Existing backup files are never overwritten.
- Restore validates the manifest, rejects unknown/duplicate/path-traversal entries, stages into a temporary sibling folder, refuses an existing destination, then moves the verified folder into place.
- Restored active auth sessions are revoked; session raw files remain byte-for-byte preserved.
- README documents the CLI and states archives are unencrypted. Encryption-at-rest and retention are open D-019 decisions.
- Added tests for verified restore, overwrite rejection, checksum-tampering rejection, and auth-session revocation. Focused result: **2 passed**.
- Latest complete verification: `pytest backend/tests/ -q` passed **37 tests** (64 warnings); syntax compilation passed for backup, backend auth/API/models, and Streamlit; `git diff --check` reported no whitespace errors (only Git line-ending notices).

### Physical Serial Integration Hardening (2026-10-21)
- On physical COM connect, the host sends `SELECT_SENSOR PIEZO` or `SELECT_SENSOR ADXL345` to align the firmware driver with the selected host adapter.
- The serial reader now ignores framed control replies and accepts only the selected sensor's data frame type. Payload sample alignment is checked; malformed payloads are counted separately from CRC errors.
- The Live Sensing start control blocks when the selected sensor differs from the connected device sensor type.
- The device page now offers only 115200 baud because firmware currently calls `Serial.begin(115200)`; other host baud options were not physically valid.
- Protocol and hardware integration docs now describe this behavior and the outstanding HIL gates.
- Verification: not run in this continuation. Physical HIL, throughput, timing, disconnect/reconnect, and sensor checks remain unverified.

### React/Vite Local Workflow Integration (2026-10-21)
- Wired the React client to the local auth endpoints with bearer tokens held in session storage, login/bootstrap, current-user validation, logout, expiry handling, and admin account management. Server-side role checks remain authoritative.
- Replaced the dashboard's auto-start simulation shortcut with a status-only overview so starting a measurement requires the explicit acquisition workflow.
- Connected device discovery/status and acquisition start/stop to the backend. Start now requires a connected sensor and sends a unique session ID, sensor-specific profile/channel, optional participant pseudonym, and optional study ID. The UI labels simulation provenance and disallows researcher connection changes.
- Replaced the sessions placeholder with backend-backed records and authenticated JSON/CSV export controls for admin/researcher roles. Added study selection, pseudonym-only prompt, acquisition quality counters, and clear research-use notices.
- Corrected the device UI to the firmware-supported 115200 baud setting; aligned synthetic analysis profile selection with sensor type; configured TypeScript JSX mode and type-only imports for `verbatimModuleSyntax`.
- `git diff --check` completed without whitespace errors (Git emitted only line-ending notices). The initial build attempt could not start because dependencies were missing; after adding a lockfile and installing dependencies, the corrected entrypoint build evidence is recorded below.
- No physical hardware/HIL or clinical validation was performed in the React continuation.

### Research Output and Raw Data Safety Updates (2026-10-21)
- Team confirmed the DOCX NPI mapping for experimental use. `NEUROPULSE_ANTIGRAVITY_MVP_MASTER_SPEC.md`, `docs/OPEN_TECHNICAL_DECISIONS.md`, and `docs/ALGORITHM_SPEC.md` now record the approval; the formula is not clinically validated.
- Earlier note: NPI score bands at 40/70 were unapproved (D-017), so the app removed categories. **Superseded by the latest team direction above:** the prototype should implement the handoff's 70/40 experimental demo bands with clear labels; clinical interpretation remains unvalidated. Cross-session average TBR/NPI summaries were removed from the Sessions view because they can mix sensor modalities.
- ADXL345 raw signed register counts are now retained alongside scaled axes and derived magnitude. Session analysis requires an explicit ADXL345 channel and uses the stored measured sample rate when available.
- Acquisition and benchmark raw writes now use exclusive file creation; session IDs are restricted to safe characters, JSON stores a canonical SHA-256, and existing raw files cannot be silently overwritten.
- Benchmark import validates finite samples, positive sample rate, and sensor/profile/channel compatibility.
- Acquisition stop/disconnect now await reader-task cancellation before persisting the raw file, avoiding a write race where samples could arrive after save. Device changes are refused while streaming.
- Verification: no tests or physical builds run during this continuation. The earlier handoff's 33-pass result is historical and does not verify these changes.

### React Build and Scaffold Entrypoint Repair (2026-10-21)
- Added `package-lock.json`; `npm ci --ignore-scripts --no-audit --no-fund` installed the exact locked frontend dependency tree (426 packages). Dependency fetching was development-time only; runtime remains local.
- Build exposed unused synthetic input state and a TypeScript option unsupported by the pinned version. Added visible controls for synthetic amplitude/noise/duration and removed the unsupported option.
- Inspected the production output and found Vite still targeted the default starter `main.ts` and `#app`, so the earlier build had not bundled the React app. Corrected `index.html` to use `main.tsx` and `#root`, removed the unused starter entry/assets, and kept the actual React renderer.
- Final `npm run build` transformed 138 modules and emitted the React application bundle (284.71 kB JS, 12.55 kB CSS). This verifies typecheck and production bundling only; browser workflow, API runtime behavior, responsive/accessibility review, and e2e remain open.
- Added two Vitest SSR checks for researcher-disabled device controls and operator-enabled connection controls; `npm run test` passed (2 tests). These are narrow role-presentation checks, not a substitute for browser/e2e or backend RBAC verification.
- A browser smoke review was attempted, but the computer-use window snapshot did not consistently match the selected Chrome tab; no browser workflow result is claimed.
- A sandboxed Windows `TestClient` run stalled while creating asyncio's loopback socketpair; its partial `FF` output was not an application test result. With local loopback access, the same Python 3.14.6 environment completed `pytest backend/tests/ -q`: **37 passed, 65 warnings in 2.10s**. The auth test includes and passed rejection of baud 921600 (HTTP 422).
- Throughput audit refined D-006 into a release blocker: current frames are 22 bytes per Piezo sample, so 1000 Hz needs ~22 kB/s, while 115200 baud 8N1 tops out at 11.52 kB/s. User directed the hardware team to decide between batching/timestamp reconstruction and supported higher baud; the technical option and timestamp model remain open pending that team decision. Do not claim Piezo 1000 Hz physical throughput until the interface is redesigned and measured on HIL.

## Readiness Gaps — Do Not Claim Commercial or Clinical Readiness
- Physical hardware is not available/verified in this workspace; board identity, wiring, ADC front-end safety/calibration, ADXL345 presence/configuration, actual sampling rate, packet loss, jitter, reconnect behavior, and long-run throughput require HIL.
- Firmware currently samples from a polling loop; target rates have not been measured. HIL timing validation remains a release gate.
- Local accounts/RBAC foundation is implemented. Login throttling, audit tamper evidence, retention, migrations, and full audit coverage still need security review before research deployment.
- No ethics approval, consent workflow/procedure, clinical protocol, advisor approval, or representative labeled dataset is present. These are external prerequisites for human/clinical studies and cannot be claimed complete by software changes.
- Piezo 1000 Hz cannot be transported by the present 115200 baud, one-sample-per-frame protocol; D-006 is deferred to the hardware team and blocks a physical MVP throughput claim until a design and HIL evidence exist.
- D-006 technical remedy is deferred to hardware team per user direction; no batching size, timestamp reconstruction model, or higher baud is approved.
- React local auth and core acquisition/session workflows are wired and production-build verified. Streamlit remains the supported launch path pending browser/runtime review. A supported continuous live refresh mechanism remains open. Stopped acquisition raw-to-session linkage is implemented and simulator-tested.
- Packaging, backup policy, cross-platform installation, and final release evidence are incomplete; a tested local backup/restore utility now exists.

### P2 — Hardware Integration (When Components Arrive)
| ID | Item | Scope |
|----|------|-------|
| **HW-01** | Physical ESP32 Flash | Flash `firmware/src/main.cpp` using PlatformIO onto ESP32 DevKit. |
| **HW-02** | Hardware-in-the-loop (HIL) | Test 115,200 baud streaming with Piezo ADC (GPIO 34) and ADXL345 (I2C GPIO 21/22). |
| **HW-03** | Circuit Calibration | Measure ADC noise floor and determine analog gain calibration constants (D-003). |

---

## ⚠️ Important Rules for AI Agents & Developers
1. **Never make medical claims:** NeuroPulse is a research tool, NOT a diagnostic medical device. Never output "Parkinson positive", "Normal/Abnormal" diagnosis.
2. **Mark simulated data:** Always tag synthetic data with `provenance: "simulated"` and label visual charts with `[MÔ PHỎNG]`.
3. **Data immutability:** Raw sensor samples in `raw.h5` / `raw.json` must never be altered or interpolated in place.
4. **Offline first:** No remote cloud dependencies, external telemetry, or paid APIs.

### UTC Timestamp Compatibility Follow-up (2026-10-21)
- Current verification environment: bundled Python 3.14.6 and workspace Node; the working tree has extensive existing changes, all preserved.
- Replaced deprecated `datetime.utcnow()` calls in backend persistence, acquisition/session lifecycle, auth expiry/revocation, and Streamlit session serialization. Backend metadata continues storing naive UTC datetimes for existing SQLite compatibility; `backend/app/db/timeutils.py` now derives them from an aware UTC clock. Added an assertion covering the SQLite timestamp convention and documented it in `docs/DATABASE_SCHEMA.md`.
- Verification after this change: `pytest backend/tests/ -q` **37 passed, 1 warning in 4.63s**. The remaining warning is Starlette's deprecation notice about using `httpx` with `TestClient`; the 64/65 datetime warnings in earlier entries are historical and superseded.
- Python compile check passed for `backend/app` and `frontend/streamlit_app.py`. React `npm run build` and `npm run test` passed earlier in this session (production bundle, 2 role-control tests); browser/e2e and real API browser integration remain unverified. `git diff --check` is clean; Git only emits line-ending notices.
- No firmware build or physical hardware/HIL validation was performed. D-006 remains deferred to the hardware team; research, security, packaging and release gates below remain open.

### Database Schema Status Clarification (2026-10-21)
- `docs/DATABASE_SCHEMA.md` now separates the target relational model from the actual six SQLAlchemy tables (`sessions`, `devices`, `studies`, `audit_events`, `local_users`, `auth_sessions`). It calls out that consent/participant and normalized processing-run tables are not implemented, raw samples live in files, and startup `create_all` is not a database upgrade mechanism.
- Next software priority: define a versioned migration baseline and a tested upgrade path for existing local databases before schema changes are treated as deployable. Do not imply the target model is already present.

### Result-First Dashboard Redesign (2026-10-21)
- Reworked the React research dashboard to a light, soft-blue desktop layout inspired by the team reference: left navigation, device status, prominent latest-session NPI, stored-session waveform, frequency spectrum, signal-quality summary and neutral previous-session comparison.
- Dashboard pulls the latest completed session and device state from the local API. Charts are generated from the stored session analysis response; no hardcoded example readings are displayed. Simulated/benchmark provenance remains visible. Empty state links to live acquisition.
- ADXL345 axis must be selected by the user (X/Y/Z) before chart analysis. Clinical Reviewer view hides sensor details, spectra, sample rates and technical integrity fields; patient remains on the separate patient portal.
- Operator was added to the same analysis and session-export API permissions as Researcher, matching the team-approved prototype role direction. This does not grant Clinical Reviewer raw signal access.
- Updated dashboard color tokens and shared UI styling. Desktop-mode frontend build succeeded after the changes (140 modules; JS 306.72 kB, CSS 22.58 kB). `git diff --check` was clean apart from Git line-ending notices. No automated tests, browser screenshot validation, Windows desktop launch, physical sensor/HIL test or clinical validation were run for this UI task.
- The Electron runtime download issue remains from the earlier desktop-shell entry; this UI change does not establish a self-contained Windows installer or make the product ready for clinical use.

### Desktop Shortcut Runtime Follow-up (2026-10-21)
- Confirmed the existing `C:\Users\Thinkpad\Desktop\NeuroPulse.lnk` points to `scripts/start.ps1`; the shortcut itself was already present and correctly targets the local launcher.
- The Electron npm wrapper was present, but `desktop/node_modules/electron/dist/electron.exe` was missing. Running `npm install` did not fetch Electron's binary artifact; the correct `npm exec -- install-electron --no` attempt failed with `TypeError: fetch failed` even with the approved command environment. Runtime download is blocked by network access to the Electron release host.
- At that point, Electron was not launchable because the official binary download failed. It was subsequently downloaded and the desktop app launch was verified in the 2026-10-22 recovery entry below. No clinical/hardware validation was performed.

### Local Desktop Launch Recovery (2026-10-22)
- Electron's Windows binary became available under `desktop/node_modules/electron/dist/electron.exe`. The initial screenshot's final Python message was informational; the actual backend failure came from using a system Python 3.14 interpreter with no Alembic installed, plus no project `.venv`.
- Created project-local `.venv` with Python 3.12 and installed `backend/requirements.txt`. The project launcher now prefers `.venv\Scripts\python.exe`, so it avoids the Windows Store Python alias and missing-system-packages issue.
- Rebuilt the desktop UI and launched Electron. Verified a responsive main window titled `NeuroPulse — Research Platform`, and local API `http://127.0.0.1:8000/api/v1/health` returned `status=ok`. The app now reaches its local sign-in screen.
- Existing local auth state requires sign-in: `bootstrap_required=false`; an active admin username is `primaryadmin`, and this system has no default password. The existing password is not available to the developer agent, so no credential was changed. Dashboard sign-in remains unverified; ask the user to enter their existing password or authorize a credential recovery workflow if they do not know it.
- Updated `scripts/build_desktop.ps1` so its last line now says whether the local Python environment was found instead of a generic pre-launch warning. Automated tests, login with credentials, and sensor/hardware checks were not run during launch recovery.
- Updated the existing Desktop shortcut to remove PowerShell's `-NoExit`, so the console will close when the launcher exits. Verified the shortcut still targets `scripts/start.ps1` from the project root.

### Sign-in Removal and Automatic Participant Code (2026-10-22)
- Team requested removal of sign-in; no local-account password is needed to enter the prototype. The desktop opens directly in the Operator mode. A persistent mode selector provides Admin, Operator, Researcher, Clinical Reviewer and Kiosk views, preserving the existing UI restrictions. These are workflow modes, **not identity verification or a security boundary**.
- The local API accepts the selected mode header only from loopback clients (the API already enforces loopback). Legacy auth endpoints and database records remain for compatibility but are no longer in the user-facing desktop flow. Before shared/networked/clinical deployment, real authentication and authorization must be restored/reviewed.
- Live Sensing now defaults to a new participant flow. On starting a measurement, operator supplies a display name and selects XX/X or XY/Y, optional birth date; the API creates the local profile, applies its existing 21-day retention, assigns the existing collision-checked patient code, then starts acquisition with that code. Existing patient codes remain supported. The generated code is displayed and retained in the form after issuance.
- Unknown/other chromosome encoding remains unresolved (D-023); current enrollment requires XX or XY and intentionally does not guess. If device/study validation fails, profile creation does not happen. If acquisition fails after profile creation, the issued participant record remains and can be reused by code.
- Files changed: `frontend/neuropulse-ui/src/App.tsx`, `frontend/neuropulse-ui/src/api/client.ts`, `frontend/neuropulse-ui/src/pages/LiveSensingPage.tsx`, `backend/app/main.py`, `docs/OPEN_TECHNICAL_DECISIONS.md`.
- Verification: `npm run build:desktop` passed (TypeScript + Vite, 140 modules); Python syntax compilation of `backend/app/main.py` passed. A local Electron run started the backend successfully and the frontend issued successful `/health`, device, sessions, and processing requests; no UI screenshot or end-to-end participant enrollment/acquisition test was performed.
- Startup follow-up: direct launch showed Windows cache permission errors in the default Roaming profile. Unpackaged Electron now stores Chromium cache/log files under ignored `data/electron-user-data/`, and desktop start uses `--disable-gpu`. Re-run the existing desktop shortcut on the user's Windows desktop to visually confirm the window remains open. The last attempted process exited after initialization; this session could not confirm that the GUI remained visible, so report this as a remaining startup verification item rather than claiming fully resolved opening.
- Docs synchronized: `README.md`, `docs/PRIVACY_AND_RESEARCH_SAFETY.md`, and `docs/OPEN_TECHNICAL_DECISIONS.md`. No automated tests were run, and no physical hardware/HIL or clinical validation was performed.

### Patient Mode, Stored Waveform, Cohort Analytics and Simulator Scenarios (2026-10-22)
- Product feedback from the user: the highlighted latest-session card must show a real micro-vibration waveform; add Patient mode as the default; staff need common patient/session statistics and cohort comparison charts; simulator should let the team compare normal-looking synthetic data and a higher 3–6 Hz energy scenario; remove placeholder/hardcoded display data in favor of actual saved records.
- Patient mode is now the app-open default, and remains selectable with Admin, Operator, Researcher, Clinical Reviewer and Kiosk. It opens the patient-code lookup/individual-history portal. Role modes remain UI/workflow modes only, not authentication.
- Overview waveform uses the saved analysis result. When a session is below the 8-second analysis window, backend provides a decimated raw preview strictly for display while preserving `INSUFFICIENT_DATA` and omitting NPI; the UI labels the trace as raw. It does not change the quality gate or overwrite stored samples.
- Added staff `Thống kê & nhóm` view backed by `/api/v1/analytics/cohorts`. Counts and cohort rows are queried from local Patient/Session records; mean NPI/TBR is per completed linked session. Cohorts compare stored age band, XX/XY marker, and diet; provenance counts and synthetic-data caveat are shown. Empty states use actual zero/empty database values, not mock rows.
- Device simulator adds `Healthy` (2 Hz, low amplitude/noise reference shape) and `Volatile` (5 Hz, greater amplitude/noise, higher 3–6 Hz energy) profiles. These selected configuration values are explicitly provisional software-demo parameters, not human-derived or clinically calibrated. `Volatile` means signal-shape scenario, not a disease/risk label. The scenario and parameters are stored in immutable raw metadata and the session notes; provenance stays `simulated`.
- Existing simulator analysis window is 8 seconds. UI tells the operator to record at least 8 seconds before stopping for NPI/quality outputs. Shorter recordings still display a raw waveform but remain analytically insufficient.
- Files changed in this follow-up: `backend/app/main.py`, `backend/app/services/acquisition/manager.py`, `backend/app/services/processing/engine.py`, `frontend/neuropulse-ui/src/App.tsx`, `frontend/neuropulse-ui/src/api/client.ts`, `frontend/neuropulse-ui/src/pages/OverviewPage.tsx`, `DevicePage.tsx`, `LiveSensingPage.tsx`, new `AnalyticsPage.tsx`, and `docs/OPEN_TECHNICAL_DECISIONS.md`.
- Verification: `scripts/build_desktop.ps1` passed and copied the latest 141-module UI bundle into `desktop/ui` (JS 309.14 kB, CSS 23.33 kB); Python syntax compilation passed for changed backend modules; `git diff --check` found no whitespace errors. No automated tests were run, no screen capture/e2e enrollment was completed, and no physical device, HIL or clinical validation was performed. D-025 is open for team review of simulation parameter values and descriptive cohort summaries.

### Patient Self-Measurement Workspace Correction (2026-10-22)
- User clarified that Patient mode is for self-measurement and must resemble the other measurement workspace, not a lookup-only portal. Patient remains the app-open default.
- Replaced patient root route with `PatientMeasurementPage`: current patient-code field, code lookup, new local profile/code creation, start/stop controls, live waveform from acquisition buffer, prominent experimental NPI, patient-friendly session quality/duration/notice, and history scoped to that profile. The patient UI omits cohort statistics, technical device details, and research/lab views.
- New/changed code cannot be edited during acquisition. Each new acquisition uses the selected code; personal history is loaded through local patient-code lookup. Patient does not get a global sessions list.
- Backend allows patient mode to create its own profile and start/stop acquisition only with the selected participant code; it checks the code exists and matches the recorded active session before stop or live-buffer reads. Historical analysis checks the session belongs to the selected code. Patient mode can read device/acquisition readiness flags needed to operate the measurement screen.
- Added master-spec section 1.7. No raw samples are overwritten, no synthetic provenance changes, and the existing 8-second pipeline quality gate remains in effect. NPI/thresholds remain experimental and explicitly non-diagnostic.
- Files changed for this correction: `backend/app/main.py`, `frontend/neuropulse-ui/src/App.tsx`, `src/api/client.ts`, new `src/pages/PatientMeasurementPage.tsx`, `src/index.css`, `desktop/ui/*`, master spec section 1.7, and this handoff.
- Verification: TypeScript desktop build passed (141 modules; JS 314.08 kB, CSS 27.46 kB); backend Python syntax compilation and FastAPI app import/OpenAPI route initialization passed (43 routes); latest UI bundle copied into `desktop/ui`; `git diff --check` passed (Git reports existing LF/CRLF notices only). First TypeScript pass caught an import-as-type issue; it was fixed and build rerun successfully. Desktop launch was attempted; the local API child logged a successful Uvicorn bind, but this execution environment denied the separate loopback health-check socket, so a stable app window/API interaction could not be confirmed. No automated tests, UI automation, visual screenshot review, device/HIL run, or clinical validation performed in this update.
- Follow-up: launch the desktop shell and verify patient profile creation, simulator start/stop, live waveform and patient-code isolation with two profiles. Validate patient session analysis with ADXL345 as well as Piezo. The code is a local lookup key, not identity authentication; do not imply clinical or production privacy guarantees.

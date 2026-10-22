# NeuroPulse — Research Platform for Micro-tremor Signal Acquisition & Analysis

> **Disclaimer:** NeuroPulse is an open-source, local-first research platform for acquiring, processing, and analyzing wrist micro-vibrations in the 3–6 Hz range. It is **NOT** a certified medical diagnostic device and does **NOT** provide medical diagnosis or therapeutic advice.

---

## 1. Project Overview

NeuroPulse is a local-first research application for acquiring, validating, storing, and analyzing wrist sensor signals. The Windows desktop shell uses the React/Vite UI in its own application window and starts the local FastAPI service alongside it. It does not open a separate browser. Streamlit remains available as a development/diagnostic interface.

`Sensor (Piezo Film / ADXL345) → ESP32 Firmware → USB Serial → Local Acquisition → Data Validation → Immutable Raw Storage → Signal Processing (SciPy) → Experimental NPI → Local Dashboard`

Key characteristics:
- **Local-first & Offline:** Operates entirely on the researcher's local machine with SQLite and local binary storage. No cloud dependencies or recurring fees.
- **Dual Hardware Support:** Supports both Sensor A (LDT0-028K Piezo Film + LM358 + ESP32 ADC) and Sensor B (ADXL345 3-Axis Digital Accelerometer + ESP32 I2C/SPI).
- **Simulation-First:** Complete synthetic signal generator and protocol simulator to develop and validate the pipeline before hardware arrives.
- **Reproducibility & Data Integrity:** Non-destructive immutable raw storage, checksum verification, and versioned signal processing / algorithm profiles.

---

## 2. Monorepo Structure

```text
neuropulse/
├── docs/                 # Specifications, architecture, protocols, and technical decisions
├── firmware/             # ESP32 C/C++ firmware (PlatformIO / ESP-IDF)
├── backend/              # Python FastAPI backend, acquisition worker, and processing engine
├── frontend/             # React desktop UI + Streamlit development dashboard
├── desktop/               # Electron Windows application shell
├── shared/               # Shared Pydantic schemas and protocol fixtures
├── data/                 # Local data directory (simulated, benchmark, sessions)
├── scripts/              # Development scripts, simulation generators, and validators
└── exports/              # Research reports and data export directory
```

---

## 3. Quick Start

### Prerequisites
- Python 3.11+
- PlatformIO Core (optional, for building ESP32 firmware)

### Environment Setup
From the repository root, create a virtual environment and install backend plus dashboard dependencies:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r backend/requirements.txt
```

### Running Backend
```powershell
python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000
```

### Running the Windows desktop app

After installing Python requirements and the frontend dependencies above, install Electron once and start NeuroPulse:

```powershell
Set-Location frontend/neuropulse-ui
npm ci
Set-Location ../../desktop
npm install
npm start
```

This builds the React interface, starts the local API, and opens a standalone NeuroPulse window. Later launches can use `scripts/start.ps1`, which now opens the desktop app by default. The app stores local data under `data/` while running from the project checkout. `NEUROPULSE_PYTHON` can point to a specific Python executable if `python` is not on PATH. This developer-run desktop shell is not yet a self-contained Windows installer; packaging the Python runtime/backend is still open.

### Running the Streamlit development dashboard

In a second terminal, from the repository root:

```bash
python -m streamlit run frontend/streamlit_app.py --server.address 127.0.0.1 --server.port 8501
```

The dashboard is available at `http://127.0.0.1:8501`; the FastAPI service listens on loopback at `http://127.0.0.1:8000`.

The current internal prototype opens without sign-in in Patient mode. Staff can select Admin, Operator, Researcher, Clinical Reviewer, or Kiosk on the local workstation; these modes only change available screens and are **not authentication or a security boundary**. The local API accepts the selected mode only from loopback clients. Do not use this mode-based prototype as a shared/networked or clinical system. The former local-account tables and auth endpoints remain for compatibility but are not used by the desktop UI. Add and review real authentication before any deployment beyond the single-machine prototype.

For a new measurement, Live Sensing can create a local participant profile and automatically issue the patient code when the operator starts the session. A name/display label and an explicit XX or XY selection are required; date of birth is optional. The code is shown in the form and attached to the acquisition. Existing patient codes can also be entered.

The Device view's simulator offers `Healthy` and `Volatile` synthetic signal scenarios. `Volatile` generates stronger 3–6 Hz energy for exercising the experimental display/alert flow; it is not a disease or patient-risk simulation. Simulator sessions and configuration metadata remain tagged `simulated`. Staff can review locally computed counts and descriptive cohort charts in **Thống kê & nhóm**. The dashboard shows a stored waveform preview even for sessions too short for analysis; the quality gate still requires the configured 8-second window before producing NPI.

### React/Vite UI (development preview)

Start the backend as above. In a second terminal:

```powershell
Set-Location frontend/neuropulse-ui
npm ci
npm run dev
```

Open `http://127.0.0.1:5173`. Vite proxies API/WebSocket requests to the loopback backend. `npm run build` creates the production bundle in `frontend/neuropulse-ui/dist`; this bundle is not yet integrated into a packaged launcher.

### Local Backup and Restore

Create an integrity-checked archive of the SQLite database and immutable session files:

```powershell
python scripts/neuropulse_backup.py backup --data-dir data --output exports/neuropulse-backup.zip
```

Restore to a **new, non-existing** data directory. The restore checks every file against the archive manifest and revokes any legacy local login sessions:

```powershell
python scripts/neuropulse_backup.py restore --archive exports/neuropulse-backup.zip --destination data-restored
```

The archive is not encrypted and contains research recordings and participant data. Keep it on storage controlled by the research team. Backup retention and encryption-at-rest requirements remain deployment decisions.

---

## 4. Documentation

- [Master Specification](Idea%20Hub/NEUROPULSE_ANTIGRAVITY_MVP_MASTER_SPEC.md)
- [Developer Handoff](Idea%20Hub/context_dev/HANDOFF.md)
- [Architecture](docs/ARCHITECTURE.md)
- [Open Technical Decisions](docs/OPEN_TECHNICAL_DECISIONS.md)
- [Data Contract](docs/DATA_CONTRACT.md)
- [Serial Protocol](docs/SERIAL_PROTOCOL.md)
- [Processing Profiles](docs/PROCESSING_PROFILES.md)
- [Algorithm Specification](docs/ALGORITHM_SPEC.md)
- [Database Schema](docs/DATABASE_SCHEMA.md)
- [Test Plan](docs/TEST_PLAN.md)
- [Hardware Integration](docs/HARDWARE_INTEGRATION.md)
- [Privacy and Research Safety](docs/PRIVACY_AND_RESEARCH_SAFETY.md)

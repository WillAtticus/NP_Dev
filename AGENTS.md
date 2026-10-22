# Agent Guidelines for NeuroPulse Development

This document defines the strict rules and workflows for AI coding agents working on the NeuroPulse project.

---

## 1. Prime Directive

Read `NEUROPULSE_ANTIGRAVITY_MVP_MASTER_SPEC.md` before making any changes. This specification is the single source of truth.

1. **Local-First & Offline:** No cloud deployments, paid external APIs, remote databases, or commercial telemetry.
2. **Data Integrity & Immutability:** Raw sensor data is immutable once written. Never overwrite, modify, or interpolate raw samples in place.
3. **Simulation-First:** Do not assume real hardware is connected. All modules must operate reliably in simulation mode.
4. **Mark Simulated Data Clearly:** Never present or export synthetic data as real human sensor data. Keep provenance strictly tagged (`simulated`, `device`, `imported_benchmark`, `reprocessed`).
5. **No Medical Claims:** NeuroPulse is a research signal processing platform, not a certified diagnostic tool. Never output automatic clinical diagnosis or risk scores.
6. **Milestone Progression:** Progress strictly through the defined milestones (M0 → M11). Never jump ahead to generate full applications without completing preceding interface definitions, tests, and documentation.
7. **Document Unresolved Decisions:** When parameters are ambiguous or contradictory, do not invent numbers or hard-code assumptions. Log them into `docs/OPEN_TECHNICAL_DECISIONS.md`.

---

## 2. Standard Task Loop

For every milestone or module task:
1. **Plan:** Review spec, identify impacted interfaces, data contracts, and tests.
2. **Implement:** Write focused code adhering to contracts.
3. **Test:** Write unit and deterministic integration tests.
4. **Review:** Check typing, linting, error states, and security.
5. **Document:** Keep `docs/` synchronized with any changes.
6. **Report:** Provide clear summary of changed files, test results, and open decisions.

---

## 3. Technology Stack Reference

- **Firmware:** C/C++ (ESP-IDF / PlatformIO)
- **Backend:** Python 3.11+ / FastAPI / Pydantic / SQLAlchemy / Alembic / SQLite
- **Signal Processing:** NumPy / SciPy (Welch PSD, Butterworth IIR, FFT)
- **Storage:** SQLite (Metadata, runs, sessions) + HDF5 / NPZ (Raw samples & processed series)
- **Frontend:** React 18+ / TypeScript / Vite / Plotly / TailwindCSS
- **Testing:** pytest (Backend) / Vitest (Frontend)

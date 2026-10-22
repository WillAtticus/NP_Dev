# NeuroPulse — Product Drift & Conformance Review

> Updated: 2026-10-22
> Workspace: `C:\Users\Thinkpad\Desktop\NeuroPulse`
> Purpose: Record approved changes from the original project description, distinguish them from unfinished implementation, and keep the next developer from treating a mockup, build, or prototype as a validated product.

## How to interpret this review

- The original references are `RTS2026 - Bản Mô tả - NeuroPulse.docx`, `NeuroPulse_Dashboard_Software_Master_Blueprint_for_Antigravity.docx`, and the initial sections of `NEUROPULSE_ANTIGRAVITY_MVP_MASTER_SPEC.md`.
- Later direct user decisions in this chat and sections 1.5–1.7 of the master spec supersede conflicting initial descriptions.
- “Implemented” means code or a UI exists. It does **not** mean the full user workflow was tested, hardware was validated, or the result is suitable for clinical use.
- This review is a repository and documentation audit. The latest React desktop build and FastAPI import/OpenAPI generation passed; the desktop's full interactive workflow could not be confirmed in this execution environment because loopback socket access was denied. No new automated tests, visual inspection, physical-device test, HIL, or clinical validation was completed for the latest patient workspace.

## Approved changes from the original description

| Original description / direction | Later approved direction | Current implementation and remaining consequence |
|---|---|---|
| The project description presents a Streamlit dashboard with Live Sensing, Benchmark/Research, and Simulation/Test as the main experience. | The user explicitly requested a desktop app that opens on the computer, not a browser/HTML workflow. | The default launcher now runs a React/Vite UI in an Electron window with a local FastAPI backend. Streamlit remains in the repository as a separate development/diagnostic UI. This is an intentional product direction change, not a completed standalone installer. |
| Blueprint asks agents to preserve the working product and avoid rewriting the UI solely to use a newer stack. | The user directly changed the target to a desktop application after encountering browser/Streamlit issues. | The React/Electron route is the active app; legacy Streamlit screens still exist and may not have feature parity. Historical references calling Streamlit the primary app are stale. |
| Blueprint describes supervised operator/research workflows and a patient portal that looks up a code. | The user clarified that Patient mode is for self-measurement and must be the default: waveform/results/history for the current patient, without global statistics, technical detail, or research results. | `PatientMeasurementPage` is now the default root route. The older `PatientPortalPage` source still exists, but is no longer routed. Patient export that was present on that old page is not available in the new route yet. |
| Earlier project materials discuss account-based roles; the team initially selected local accounts with roles. | The user later explicitly asked to restore access without sign-in. Staff select a mode on the computer; the system should auto-issue a patient code for a new profile/session. | The prototype has no sign-in screen. API mode headers and UI restrictions are workflow controls only. They do not authenticate a staff member or protect data from another person using the same workstation. This is an approved prototype simplification, not production access control. |
| Early descriptions lean toward patient lookup and later B2B/B2C commercialization, with possible multi-machine service. | The user said the immediate version is local on Windows 10/11, for internal trials, science fairs, competitions, and fundraising; no sync/database service is needed yet. | Data is local to the machine. Cross-machine lookup, cloud, SaaS, multi-site operation, installer-based rollout, and commercial operations are intentionally outside the present prototype. |
| Early description emphasizes the Piezo example and 1000 Hz acquisition; later hardware notes also describe ADXL345. | The team will compare both component configurations, while the hardware team decides how to resolve the 115200-baud Piezo throughput shortfall. | Both software sensor profiles and simulator paths exist. The physical Piezo target is still not supportable at 1000 Hz over the current one-sample-per-frame, 115200 8N1 link; no hardware decision/HIL evidence has closed D-006. |
| Original presentation describes NPI thresholds as preliminary/unvalidated and risks overstating screening claims. | The user approved use of the team's formula and 40/70 demo bands for experimental display, with explicit non-clinical labeling. | NPI and demo bands are implemented as experimental outputs. They are not sensitivity/specificity estimates, disease probabilities, validated risk scores, or diagnoses. Clinical interpretation remains unapproved. |
| The original profile/code descriptions changed during conversation. | The user clarified `X` means XX and `Y` means XY, removed birth-year digits, and selected a random suffix pool `00001–99999`; the format still includes age band and measurement-year segment. | Code generation exists with collision checks. The current code uses profile creation year rather than the first actual measurement; other/unknown chromosome cases and some age/century rules remain open in D-020/D-023. |
| Initial app descriptions mention retaining and following patient data but do not fully specify local retention. | The user specified 3-week retention by default and an indefinite research-retention setting. | Expiry timestamps, Admin retention toggle, and periodic purge exist. This is local single-machine retention; it is not an institutional data retention or backup policy. |
| UI reference image marks waveform (yellow), NPI (dark blue), session details (light blue), patient code (red), and start action (green). | The user gave these placements as the intended measurement-first layout. | The current patient page has the right functional sections, but does **not** reproduce the marked placement: the start button is sticky at the bottom rather than in the marked green header area; NPI appears below the waveform; the code is in a full-width bar. Treat the spatial mapping as unfinished UI conformance. |

## Current implementation compared with the requested product

### Present in the codebase

- **Windows desktop path:** Electron shell, React/TypeScript UI, local FastAPI child process, and `scripts/start.ps1` launcher. React is built and copied into `desktop/ui`.
- **Local data path:** SQLite metadata plus HDF5/JSON recordings, session records, hashes/provenance, profile records, patient-code lookup, and local backup/restore utility.
- **Patient self-measurement foundation:** default Patient mode, patient-code input/lookup, simple profile creation and code issuance, measurement start/stop, polling of the acquisition live buffer, personal session history, experimental NPI display after analysis, and profile-scoped history requests.
- **Staff research foundation:** device page, simulator choice (`Healthy`/`Volatile`), live sensing workflow, signal analysis, algorithm lab, sessions, patient registry, and local cohort analytics.
- **Signal-processing foundation:** Piezo and ADXL345 profiles/adapters, filtering/PSD/TBR pipeline, minimum-window quality gate, NPI formula and experimental category bands. Synthetic inputs retain simulated provenance.
- **Retention foundation:** 21-day profile expiry, an Admin indefinite-retention switch, and startup/hourly cleanup of expired profile/session files. Cleanup skips a recording while it is active and removes it on a later pass.
- **Documentation:** data contract, architecture, privacy/research safeguards, hardware integration, test plan, and open technical decision log.

### Partially implemented or mismatched with the chat/spec

| Expected outcome | Current evidence | Gap / risk |
|---|---|---|
| Patient can self-measure with the same central waveform/result experience as the staff view. | New Patient root page gets live samples from `/acquisition/live-buffer` and shows the latest stored analysis. | Live waveform is raw channel data and is polled once per second; it is not the post-filtered trace. There is no live NPI calculation; while recording, the NPI panel says it is collecting and analysis runs after stop. The screenshot's green start-button placement is not followed. |
| Patient can create a profile with the requested clinical details. | Staff registry has name, DOB, XX/XY, personal/family history, diet. Patient self-registration currently asks only name, DOB, and XX/XY. | Patient-created profiles omit the requested clinical/family history and diet unless staff creates the profile first. No profile edit flow was found in the current React route. |
| Patient can export their individual record and measurements. | The orphaned old `PatientPortalPage.tsx` contains a profile JSON download button. | That component is no longer routed; the new Patient page has no export action. `/sessions/{id}/export` is staff-only and session-scoped, not patient-code-scoped. Patient export is currently missing. |
| Patient gets a clear, patient-friendly result, warning, live plot and history. | New page shows waveform, NPI category, duration/quality text, and session list. | The page displays a raw quality enum in the chart footer in some states; the live NPI is absent; latest view does not show all profile details; alert copy needs a human-factor and clinical-advisor review. |
| Patient code automatically scopes each measurement and history. | Frontend stores the selected code; start request attaches it; lookup returns sessions for that code; patient live-buffer, stop, and analysis paths check code/session linkage. | This is local workflow scoping only. A patient code is not identity proof; anyone with the code and local API access can look up that record. No real authentication is intentionally enabled. Multi-profile isolation has not been integration-tested in the latest build. |
| Admin, Operator, Researcher, and Clinical Reviewer can perform role-appropriate research actions, including export/delete. | Staff navigation and mode-specific pages exist; all staff modes can see cohort summaries, with role restrictions on some pages/actions. | Delete endpoint is Admin-only. Session export allows Admin/Operator/Researcher but excludes Clinical Reviewer. This differs from the user's request that these staff modes can export/delete all data. There is no bulk export/delete workflow. Reviewer fields are partly hidden in UI, but some API responses still carry full session fields; UI hiding is not data minimization. |
| Staff see group-level database charts. | `/analytics/cohorts` computes patient/session counts and grouped statistics by age band, chromosome marker, and diet. The React page charts counts and mean NPI by age and chromosome. | Diet is returned by the API but not charted in the UI; analysis is a small set of descriptive summaries, not the complete research/statistics workspace described by the team. Stored groups can mix simulated/imported data unless users inspect provenance. |
| Researchers can reproduce an analysis later. | Profiles, NPI algorithm metadata, session provenance, raw hashes, and some parameter/config info exist. | The target normalized `processing_runs`/`algorithm_runs` model and immutable per-run parameter snapshots are not implemented as full persisted entities. Re-analysis can return a result without a complete, durable run/version history. Audit event coverage is not exhaustive. |
| Both hardware options are ready to connect. | Serial adapters/parser and simulator paths exist in software. | No board/firmware/sensor HIL is demonstrated. The Piezo serial throughput contradiction is open and release-blocking for the stated 1000 Hz target. ADXL345 physical ODR/units/scaling and Piezo calibration are not verified. |
| The app is easy to install/open on a clean Windows 10/11 computer. | Desktop source shell and UI build work in this workspace; the Python virtual environment exists here. | There is no standalone installer/package. `npm start` rebuilds the UI; the app depends on Node/npm, Electron dependencies, Python and backend requirements in the project environment. Clean-machine installation, data path, upgrade/uninstall and Windows 10/11 coverage remain unverified. |
| The latest patient workflow has been tested end-to-end. | TypeScript desktop build passed (141 modules); Python syntax compile and FastAPI import/OpenAPI generation passed (43 routes / 32 paths); whitespace check passed. | No new automated patient-workflow tests were run. No visual QA, desktop runtime workflow, simulator recording, two-code isolation, ADXL patient analysis, physical device, or HIL test was completed after the latest changes. |

## Still missing before the prototype matches the user's expected workflow

### Product and UI

1. Match the marked layout: place the start/stop action in the intended green region; align code, NPI, waveform, and session-detail panels to the reference.
2. Restore patient export in the new Patient workspace, with an API that exports only that code's personal profile/history/raw measurement data.
3. Decide and implement whether NPI is meant to be calculated live after the 8-second minimum window or only after stopping. Do not weaken the quality gate to make the UI appear live.
4. Complete patient profile fields and a patient-friendly profile/history view, including the fields the user requested.
5. Add/finish the researcher group charts for diet and the other agreed comparisons; add provenance filters or clearly separated cohorts so simulated/imported records cannot be mistaken for participant data.
6. Reconcile staff permissions: export/delete permissions for Operator, Researcher, Clinical Reviewer, and Admin; distinguish UI restrictions from API response minimization.

### Engineering and evidence

1. Run deterministic backend/frontend tests for profile creation, code-scoped start/stop/live reads, history, export, retention cleanup, and role boundaries. Current latest-work verification is build/import only.
2. Launch Electron on the target Windows workstation and manually verify profile creation → simulator/device connect → at least 8-second measurement → stop/save → waveform/NPI/alert/history → reopen by code. Repeat for two patient codes and both sensor profiles.
3. Resolve D-006 with the hardware team; measure actual sample rate, loss, jitter, timing and recovery on the final Piezo path. Validate ADXL345 units/ODR/range separately.
4. Complete clean Windows install/upgrade/uninstall and offline startup; produce a signed or otherwise distributable package only after dependency and data-path decisions.
5. Persist processing/algorithm run versions and configuration snapshots; complete audit coverage and verify backup/restore policy for research data.

### Clinical/research readiness (separate from software completion)

- A running app and NPI output are not evidence of Parkinson's screening performance. No sensitivity/specificity/AUC, clinical cutoff validation, calibration study, or external validation is evidenced in the repository.
- Before real participant measurement, the team still needs qualified clinical/research supervision, approved protocol and participant information/consent process, applicable ethics/IRB or local approvals, privacy/data-retention governance, and safe/verified hardware procedures.
- The simulator's `Healthy`/`Volatile` profiles are software signal scenarios only. `Volatile` is not a patient-risk model and cannot represent a real patient group.
- Therefore the present app is an internal research/demo prototype, **not** commercial-ready, a medical device, a clinical decision tool, or ready for unsupervised clinical testing.

## Known stale or contradictory context to correct on the next handoff pass

- Older `HANDOFF.md` sections still call Streamlit the primary UI, describe the old patient page as the active portal, and contain older launch instructions claiming the desktop shortcut starts Streamlit. The current default launcher is `scripts/start.ps1` → Electron/React. Historical sections are retained as history; use the latest status section and this file for current behavior.
- Several older handoff paragraphs report retention cleanup as unfinished even though `backend/app/services/retention.py` and the backend startup/hourly cleanup loop now exist. The exact retention edge cases still need tests, but the feature is not wholly absent.
- Master-spec backlog and release checklist boxes are still unchecked wholesale. They are planning checklists, not a reliable status dashboard; reconcile them against code and test evidence before marking any item done.
- The app still contains legacy Streamlit and old patient-portal code. Do not assume those screens are part of the default Electron app or have parity with the current React pages.

## Summary judgment

The implementation has a real local full-stack foundation and meaningful simulation, signal-processing, patient-code, staff analytics, and desktop-shell code. The last patient-mode correction moved the UI toward the requested self-measurement flow. The highest immediate product gaps are patient export, the annotated start-button/layout mismatch, missing live NPI behavior, incomplete patient profile form, and staff permission mismatch. The highest release risks remain lack of end-to-end workflow verification, no standalone installer, unresolved physical serial throughput/calibration, and no clinical validation/approval. Keep all NPI and threshold language explicitly experimental.

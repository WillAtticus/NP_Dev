# NeuroPulse transfer package

Source handoff snapshot for another developer or AI coding agent. It includes application source, firmware, development scripts, project docs, Idea Hub specifications/context, synthetic reference inputs, and local Git history/index. It is not an installer and does not contain Python/Node dependencies.

## Start here
1. Read `AGENTS.md`.
2. Read `Idea Hub/NEUROPULSE_ANTIGRAVITY_MVP_MASTER_SPEC.md` completely.
3. Read `Idea Hub/context_dev/HANDOFF.md`, `drift-away.md`, and `implementation plan 0.1.md`.
4. Review `git status` and the current diff before editing. The source checkout had uncommitted changes when this snapshot was assembled.
5. Follow `README.md` for Windows setup. Python and Node dependencies must be installed on the receiving machine; the desktop shell is a developer-run build, not a self-contained installer.

## Deliberately excluded
- `.venv`, all `node_modules`, caches, compiled UI/build outputs, and PlatformIO build artifacts.
- Local SQLite database, participant/session recordings, exports, Electron user data, and backup archives. These can contain sensitive data and should not be shared casually.
- Machine-specific AVG exclusion helper.

Synthetic reference files under `data/simulated` are retained; they are generated/test inputs, not human measurements. Runtime folders are only empty placeholders where present in source control.

## GitHub
Git history is included. The original checkout had no Git remote configured. Before publishing, inspect the full diff and history for secrets, personal data, licensing, and files that should not be public; configure the intended remote and visibility explicitly. Never publish participant data or local database/backup files.

## Scope and safety
NeuroPulse is a local research prototype. NPI and threshold bands are experimental, not clinically validated, and do not diagnose Parkinson's or provide medical advice. Hardware throughput, calibration, HIL, research approvals, clean-machine installer, and clinical validation remain open as recorded in the handoff/plan.

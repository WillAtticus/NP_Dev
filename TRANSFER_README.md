# NeuroPulse transfer package

Updated source snapshot for another developer/AI agent or a GitHub repository. It includes app/backend/frontend source, firmware, migrations, tests, scripts, project specifications, Idea Hub context, and safe synthetic reference files. It is not an installer or a clinically validated product.

## Start here
1. Read `AGENTS.md` and `Idea Hub/NEUROPULSE_ANTIGRAVITY_MVP_MASTER_SPEC.md`.
2. Read `Idea Hub/context_dev/HANDOFF.md`, `drift-away.md`, and `implementation plan 0.1.md`.
3. Read `README.md`, then check `git status` and the diff before changing code.
4. Follow the Windows setup instructions in `README.md`. Dependencies and a clean-machine installer are not bundled.

## Excluded from this package
Python/Node environments, build outputs, caches, machine-specific settings, local databases, raw recordings, exports and backup archives are omitted. Synthetic fixtures under `data/simulated` are retained and must stay labeled synthetic.

The existing `.git` directory in the Desktop transfer folder is preserved. The SHA-256 manifest covers transferred project files but excludes Git internals and the manifest itself.

## GitHub and safety
Before publishing, inspect the full diff and Git history for secrets, personal information, licensing, and files that should not be public. No remote is configured by this transfer operation. Do not publish participant data, raw recordings, databases, or backups.

NeuroPulse remains a local research prototype. NPI and alert bands are experimental and are not clinical diagnoses or validated risk estimates. Physical MVP/HIL, launch reliability, hardware throughput, expert review, clinical validation, and commercial/regulatory readiness remain open; see the handoff and implementation plan.

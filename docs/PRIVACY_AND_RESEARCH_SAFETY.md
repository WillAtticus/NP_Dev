# Privacy, Governance & Research Safety — NeuroPulse MVP

---

## 1. Principles

1. **Prototype Purpose and Limits:**
   NeuroPulse's internal prototype supports exploratory research and a patient-facing screening demo requested by the team. It is **not** a certified medical diagnostic device, and its screening bands are not clinically validated.
2. **Prototype Patient Records:**
   The team has requested names, dates of birth, and clinical history in local prototype patient records. Patient codes are lookup keys, not authentication or anonymization. Keep personal identifiers out of aggregate research exports unless needed, and apply the team's three-week retention/optional indefinite research retention policy.
   Profiles and linked non-active sessions/raw files are purged at backend startup and hourly after the configured 21-day expiry. Active recording sessions are retained until recording stops and a later cleanup pass runs. Admin's indefinite-retention option excludes a profile and its linked data from this cleanup.
3. **Experimental Patient Screening Demo:**
   Per the latest team direction (2026-10-21), the internal prototype may show patient-specific NPI demo bands and alerts: `>=70` experimental reference range, `40–69` experimental monitoring, and `<40` outside experimental reference range. Display these only as the team's unvalidated research hypothesis, with a clear experimental/non-clinical notice and algorithm/rule version. Never call them a diagnosis, probability of Parkinson's, or clinically validated risk. This supersedes the earlier D-017 instruction to hide the bands in the prototype; clinical use still requires advisor review and validation.
4. **Local Data Custody:**
   All recordings and databases remain strictly on the local researcher workstation. No analytics or metrics are transmitted externally.

## 2. Prototype access modes (internal demo only)

- Patients enter their patient code to open a personal record. Staff selects an Admin, Researcher, Operator, or Clinical Reviewer mode on the local machine.
- These modes limit UI actions only and are not authentication or a security boundary. This is acceptable only for the current controlled internal prototype; implement identity verification and stronger access control before deployment in a hospital or to consumers.
- Patients can view/export only their own data. Staff modes can view/export/delete the wider dataset according to the prototype direction.

## 3. Local account controls (future deployment foundation)

- Current internal prototype opens without sign-in. Staff select an operation mode on the workstation. Mode selection changes available UI/API operations but does not authenticate a person and is not a security boundary.
- Auth account/session tables and endpoints remain as legacy infrastructure, but the desktop UI does not use them. Local API requests remain restricted to loopback; this does not protect against another person using the same workstation.
- Before shared/networked, commercial, or clinical use, implement and review real identity verification, authentication, role authorization, session management, audit and recovery controls. Do not rely on prototype modes to protect participant data.
- The existing local-account implementation is retained as the current code state, but it does not fully match the newly selected prototype mode-switch workflow. Do not assume UI mode selection enforces server-side authorization; reconcile this before deployment beyond a controlled demo.
- Authenticated API and WebSocket requests are restricted to loopback clients. The supported launch configuration binds the service to `127.0.0.1`.
- Measurement lifecycle actions create local audit events. Legacy account events may exist in databases created by previous prototype builds.
- These controls are an MVP foundation, not a completed workstation threat model. Login throttling, audit-log tamper evidence, OS account hardening, and deployment security review remain open before human research use.

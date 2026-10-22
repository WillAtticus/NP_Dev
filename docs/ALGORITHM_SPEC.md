# Algorithm Specification & NPI Formula — NeuroPulse MVP

---

## 1. Overview & Disclaimer

The NeuroPulse Index (NPI) is an experimental research metric proposed to quantify the relative power concentration of micro-vibrations in the 3–6 Hz frequency band compared to baseline activity.
**NPI is NOT a validated clinical biomarker, NOT a diagnosis of Parkinson's disease, and NOT a clinical risk score.**

---

## 2. Mathematical Definition

### 2.1. Tremor Band Ratio (TBR)
Let $S_{xx}(f)$ be the Power Spectral Density (PSD) computed via Welch's method.
The power in band $[f_1, f_2]$ is given by numerical integration:
$$P_{[f_1, f_2]} = \int_{f_1}^{f_2} S_{xx}(f) \, df$$

The Tremor Band Ratio ($\text{TBR}$) is:
$$\text{TBR} = \frac{P_{[3.0, 6.0]}}{P_{[1.0, 20.0]}}$$

### 2.2. NeuroPulse Index (NPI)
Approved by the project team on 2026-10-21 for experimental research use (see D-009 in `OPEN_TECHNICAL_DECISIONS.md`):

$$\text{NPI} = 100 \times \left[ 1 - \text{clip}\left(\frac{\text{TBR} - \text{TBR}_{\min}}{\text{TBR}_{\max} - \text{TBR}_{\min}}, 0, 1\right) \right]$$

Where:
- $\text{TBR}_{\min} = 0.40$ (Default baseline constant)
- $\text{TBR}_{\max} = 0.85$ (Default baseline constant)
- $\text{clip}(x, 0, 1) = \max(0, \min(1, x))$

### 2.3. Behavior
- When $\text{TBR} \le 0.40 \implies \text{NPI} = 100.0$
- When $\text{TBR} \ge 0.85 \implies \text{NPI} = 0.0$
- In intermediate ranges, $\text{NPI}$ scales linearly from 100 down to 0.

### 2.4. Score Bands
Team direction for the internal prototype (2026-10-21) authorizes demo categories using the earlier handoff's thresholds: `>=70` experimental reference range, `40–69` experimental monitoring, `<40` outside experimental reference range. The UI may issue a demo alert from these thresholds, but must label the rule as an unvalidated research hypothesis and persist its rule version. These bands are not clinically validated and must not be described as a diagnosis, disease probability, or validated risk. See D-017.

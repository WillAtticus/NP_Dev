"""
Algorithm Registry & NPI Engine — NeuroPulse MVP

NPI_v1_baseline: Implements the formula extracted from the project Word document:
    TBR = power(3-6 Hz) / power(1-20 Hz)
    NPI = 100 × [1 − clip((TBR − tbr_min) / (tbr_max − tbr_min), 0, 1)]

IMPORTANT: NPI is an experimental research index.
It is NOT a medical diagnostic score and does NOT classify individuals as
healthy or diseased. Always display with appropriate research disclaimers.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


# ─────────────────────────────────────────────────────────────────────────────
# Algorithm status definitions
# ─────────────────────────────────────────────────────────────────────────────
class AlgorithmStatus:
    DRAFT              = "draft"
    EXPERIMENTAL       = "experimental"
    APPROVED_RESEARCH  = "approved_for_research"
    RETIRED            = "retired"
    FORMULA_PENDING    = "formula_pending"


# ─────────────────────────────────────────────────────────────────────────────
# ─────────────────────────────────────────────────────────────────────────────
# Algorithm definitions
# ─────────────────────────────────────────────────────────────────────────────
@dataclass
class AlgorithmVersion:
    algorithm_id:   str
    version:        str
    display_name:   str
    description:    str
    status:         str
    sensor_compat:  List[str]
    parameters_schema: Dict[str, Any]
    default_parameters: Dict[str, Any]
    formula_reference: str
    validation_notes: str = ""
    change_notes: str = ""


NPI_V1_BASELINE = AlgorithmVersion(
    algorithm_id="NPI",
    version="1.0.0",
    display_name="NPI v1 Baseline (Experimental)",
    description=(
        "Experimental NeuroPulse Index derived from the Tremor Band Ratio (TBR).\n"
        "TBR = power(3–6 Hz) / power(1–20 Hz).\n"
        "NPI = 100 × [1 − clip((TBR − tbr_min)/(tbr_max − tbr_min), 0, 1)].\n\n"
        "⚠ RESEARCH USE ONLY. Not a validated clinical diagnostic. "
        "Parameters tbr_min=0.40 and tbr_max=0.85 are initial experimental constants "
        "requiring calibration on real human data."
    ),
    status=AlgorithmStatus.EXPERIMENTAL,
    sensor_compat=["PIEZO_LDT0_028K", "ADXL345"],
    parameters_schema={
        "tbr_min": {"type": "float", "description": "TBR value mapping to NPI=100", "default": 0.40},
        "tbr_max": {"type": "float", "description": "TBR value mapping to NPI=0", "default": 0.85},
    },
    default_parameters={"tbr_min": 0.40, "tbr_max": 0.85},
    formula_reference="docs/ALGORITHM_SPEC.md",
    validation_notes=(
        "Constants 0.40 and 0.85 are software-testing initial values extracted from "
        "project specification document (Office OpenXML MathML). "
        "Must be calibrated from real-world clinical dataset before any research conclusion."
    ),
    change_notes="Initial baseline extracted from project Word document.",
)


# ─────────────────────────────────────────────────────────────────────────────
# Algorithm Registry
# ─────────────────────────────────────────────────────────────────────────────
class AlgorithmRegistry:
    _registry: Dict[str, Dict[str, AlgorithmVersion]] = {}

    @classmethod
    def register(cls, algo: AlgorithmVersion):
        if algo.algorithm_id not in cls._registry:
            cls._registry[algo.algorithm_id] = {}
        cls._registry[algo.algorithm_id][algo.version] = algo

    @classmethod
    def get(cls, algorithm_id: str, version: str) -> Optional[AlgorithmVersion]:
        return cls._registry.get(algorithm_id, {}).get(version)

    @classmethod
    def list_all(cls) -> List[Dict[str, Any]]:
        result = []
        for algo_id, versions in cls._registry.items():
            for ver, algo in versions.items():
                result.append({
                    "algorithm_id": algo.algorithm_id,
                    "version": algo.version,
                    "display_name": algo.display_name,
                    "status": algo.status,
                    "sensor_compat": algo.sensor_compat,
                    "default_parameters": algo.default_parameters,
                })
        return result


# Register built-in algorithms
AlgorithmRegistry.register(NPI_V1_BASELINE)


# ─────────────────────────────────────────────────────────────────────────────
# Algorithm execution
# ─────────────────────────────────────────────────────────────────────────────

def run_npi(
    tbr: Optional[float],
    parameters: Optional[Dict[str, float]] = None,
    quality_status: str = "VALID_FOR_ANALYSIS",
) -> Dict[str, Any]:
    """
    Execute the NPI_v1_baseline formula.

    Returns dict with npi_value, tbr, category, quality_status, warnings.
    NPI is NOT computed if quality_status is INVALID or INSUFFICIENT_DATA.
    """
    params = parameters or NPI_V1_BASELINE.default_parameters
    tbr_min = float(params.get("tbr_min", 0.40))
    tbr_max = float(params.get("tbr_max", 0.85))

    warnings: List[str] = [
        "⚠ RESEARCH / EXPERIMENTAL — NOT FOR DIAGNOSIS",
        "NPI is an experimental index. Reference ranges are uncalibrated initial values.",
    ]

    # Guard: do not produce NPI for invalid windows
    if quality_status in ("INVALID", "INSUFFICIENT_DATA"):
        return {
            "npi_value": None,
            "tbr": tbr,
            "category": None,
            "screening_alert": None,
            "quality_status": quality_status,
            "algorithm_id": "NPI",
            "algorithm_version": "1.0.0",
            "parameter_snapshot": params,
            "warnings": warnings,
        }

    if tbr is None:
        return {
            "npi_value": None,
            "tbr": None,
            "category": None,
            "screening_alert": None,
            "quality_status": quality_status,
            "algorithm_id": "NPI",
            "algorithm_version": "1.0.0",
            "parameter_snapshot": params,
            "warnings": warnings + ["TBR could not be computed (zero reference band power)."],
        }

    # ── NPI formula ──────────────────────────────────────────────────────────
    #   NPI = 100 × [1 − clip((TBR − tbr_min) / (tbr_max − tbr_min), 0, 1)]
    denom = tbr_max - tbr_min
    if denom <= 0:
        raise ValueError(f"Invalid parameters: tbr_max ({tbr_max}) must be > tbr_min ({tbr_min})")

    normalised = (tbr - tbr_min) / denom
    clipped    = max(0.0, min(1.0, normalised))
    npi_value  = round(100.0 * (1.0 - clipped), 2)

    if quality_status == "WARNING":
        warnings.append("Window quality is WARNING — result shown with caution.")

    # Team-approved-for-demo research hypothesis carried from the project handoff.
    # These are experimental display bands, not clinically validated thresholds.
    if npi_value >= 70:
        category = "experimental_reference_range"
        screening_alert = "none"
    elif npi_value >= 40:
        category = "experimental_monitoring"
        screening_alert = "review"
    else:
        category = "outside_experimental_reference_range"
        screening_alert = "attention"

    return {
        "npi_value": npi_value,
        "tbr": round(tbr, 6),
        "category": category,
        "screening_alert": screening_alert,
        "screening_rule_version": "NPI_DEMO_BANDS_40_70_v1",
        "quality_status": quality_status,
        "algorithm_id": "NPI",
        "algorithm_version": "1.0.0",
        "parameter_snapshot": params,
        "warnings": warnings,
    }

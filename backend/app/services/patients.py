"""Patient-code generation for the single-machine prototype."""
from __future__ import annotations

import secrets
from datetime import date
from typing import Callable, Optional

from sqlalchemy.orm import Session

try:
    from ..db.models import Patient
except ImportError:
    from backend.app.db.models import Patient


AGE_BANDS = {"I", "C", "J", "Y", "M", "E"}
CHROMOSOME_MARKERS = {"X", "Y"}


def age_band_for(date_of_birth: Optional[date], at_date: date) -> str:
    if date_of_birth is None:
        return "I"
    age = at_date.year - date_of_birth.year - (
        (at_date.month, at_date.day) < (date_of_birth.month, date_of_birth.day)
    )
    if age < 0:
        raise ValueError("Date of birth cannot be after the first measurement date.")
    if age < 10:
        return "C"
    if age < 18:
        return "J"
    if age < 30:
        return "Y"
    if age < 50:
        return "M"
    return "E"


def generate_patient_code(
    db: Session,
    chromosome_marker: str,
    age_band: str,
    first_measurement_date: date,
    *,
    random_number: Optional[Callable[[], int]] = None,
    max_attempts: int = 1000,
) -> str:
    marker = chromosome_marker.upper()
    if marker not in CHROMOSOME_MARKERS:
        raise ValueError("Chromosome marker must be X (XX) or Y (XY).")
    if age_band not in AGE_BANDS:
        raise ValueError("Unsupported age band.")
    random_number = random_number or (lambda: secrets.randbelow(99_999) + 1)
    for _ in range(max_attempts):
        suffix = random_number()
        if not 1 <= suffix <= 99_999:
            raise ValueError("Random suffix must be between 00001 and 99999.")
        code = f"N{marker}{age_band}{first_measurement_date:%y}{suffix:05d}"
        if db.query(Patient.id).filter(Patient.patient_code == code).first() is None:
            return code
    raise RuntimeError("Could not allocate a unique patient code after repeated collisions.")

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field, fields
from pathlib import Path

from pydantic import BaseModel, Field, model_validator


@dataclass(slots=True)
class CalibrationConfig:
    """Server-side calibration configuration for quality scores and CL calculation."""
    rating_weight: float = 0.45
    proof_weight: float = 0.20
    discussion_weight: float = 0.20
    persistence_weight: float = 0.15
    showmanship_cap: float = 0.6
    cl_cap: float = 3.0
    cl_k1: float = 2.0
    cl_k2: float = 2.0
    low_confidence_threshold: int = 40
    medium_confidence_threshold: int = 70
    missing_source_threshold: int = 3


CALIBRATION_CONFIG_PATH = Path(__file__).resolve().parent.parent / "data" / "calibration_config.json"

DEFAULT_CONFIG = CalibrationConfig()


def load_calibration_config() -> CalibrationConfig:
    if CALIBRATION_CONFIG_PATH.exists():
        try:
            raw = json.loads(CALIBRATION_CONFIG_PATH.read_text(encoding="utf-8"))
            known_keys = {f.name for f in fields(CalibrationConfig)}
            filtered = {k: v for k, v in raw.items() if k in known_keys}
            if filtered:
                return CalibrationConfig(**filtered)
        except (json.JSONDecodeError, TypeError, ValueError):
            pass
    return CalibrationConfig()


def save_calibration_config(cfg: CalibrationConfig) -> None:
    CALIBRATION_CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    CALIBRATION_CONFIG_PATH.write_text(
        json.dumps(asdict(cfg), indent=2, ensure_ascii=False), encoding="utf-8"
    )


class CalibrationUpdate(BaseModel):
    rating_weight: float | None = Field(default=None, ge=0, le=1)
    proof_weight: float | None = Field(default=None, ge=0, le=1)
    discussion_weight: float | None = Field(default=None, ge=0, le=1)
    persistence_weight: float | None = Field(default=None, ge=0, le=1)
    showmanship_cap: float | None = Field(default=None, ge=0.1, le=1.0)
    cl_cap: float | None = Field(default=None, ge=1.0, le=5.0)
    cl_k1: float | None = Field(default=None, ge=0, le=5.0)
    cl_k2: float | None = Field(default=None, ge=0, le=5.0)
    low_confidence_threshold: int | None = Field(default=None, ge=0, le=99)
    medium_confidence_threshold: int | None = Field(default=None, ge=10, le=99)
    missing_source_threshold: int | None = Field(default=None, ge=1, le=10)

    @model_validator(mode="after")
    def _validate_weight_sum(self) -> "CalibrationUpdate":
        """Validate that all four quality weights sum to 1.0 ± 0.01."""
        weights = [
            self.rating_weight,
            self.proof_weight,
            self.discussion_weight,
            self.persistence_weight,
        ]
        provided = [w for w in weights if w is not None]
        if len(provided) == 4:
            total = sum(provided)
            if abs(total - 1.0) > 0.01:
                raise ValueError(
                    f"Quality weight proportions must sum to 1.0 (got {total:.4f}). "
                    f"Provided weights: rating_weight={self.rating_weight}, "
                    f"proof_weight={self.proof_weight}, "
                    f"discussion_weight={self.discussion_weight}, "
                    f"persistence_weight={self.persistence_weight}"
                )
        return self


def get_allowed_origins() -> list[str]:
    raw_value = os.getenv("ALLOW_ORIGINS", "*").strip()
    if not raw_value or raw_value == "*":
        return ["*"]
    return [item.strip() for item in raw_value.split(",") if item.strip()]


def get_frontend_backend_url() -> str:
    return os.getenv("FRONTEND_BACKEND_URL", "").strip()

from __future__ import annotations

import os


def get_allowed_origins() -> list[str]:
    raw_value = os.getenv("ALLOW_ORIGINS", "*").strip()
    if not raw_value or raw_value == "*":
        return ["*"]
    return [item.strip() for item in raw_value.split(",") if item.strip()]


def get_frontend_backend_url() -> str:
    return os.getenv("FRONTEND_BACKEND_URL", "").strip()

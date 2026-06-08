"""Persist and load prediction records as local JSON files."""

from __future__ import annotations

import gc
import json
import uuid
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

from steam_publisher_predictor.models import SalesBreakdown

DEFAULT_DATA_DIR = Path(__file__).resolve().parent.parent.parent.parent / "data"


def _record_to_dict(breakdown: SalesBreakdown) -> dict:
    """Serialize a SalesBreakdown into a flat dict suitable for JSON storage."""
    data = asdict(breakdown)
    # Store the query as a reference
    data["query"] = breakdown.game.name
    return data


def save_prediction_record(
    breakdown: SalesBreakdown,
    query: str,
    data_dir: Path | None = None,
) -> Path:
    """Persist a prediction record to a local JSON file.

    Returns the path to the saved file.
    """
    data_dir = data_dir or DEFAULT_DATA_DIR
    data_dir.mkdir(parents=True, exist_ok=True)

    record_id = uuid.uuid4().hex[:12]
    timestamp = datetime.now(timezone.utc).isoformat()

    record = {
        "record_id": record_id,
        "query": query,
        "created_at": timestamp,
        "game": {
            "app_id": breakdown.game.app_id,
            "name": breakdown.game.name,
            "url": breakdown.game.url,
            "price_usd": breakdown.game.price_usd,
            "release_date": breakdown.game.release_date,
        },
        "analysis": _record_to_dict(breakdown),
    }

    filename = f"prediction_{record_id}.json"
    filepath = data_dir / filename
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(record, f, indent=2, ensure_ascii=False)

    return filepath


def load_record(record_id: str, data_dir: Path | None = None) -> dict | None:
    """Load a prediction record by record_id. Returns None if not found."""
    data_dir = data_dir or DEFAULT_DATA_DIR
    if not data_dir.exists():
        return None

    for filepath in list(data_dir.glob("prediction_*.json")):
        with open(filepath, "r", encoding="utf-8") as f:
            try:
                data = json.load(f)
                if data.get("record_id") == record_id:
                    return data
            except json.JSONDecodeError:
                continue
    return None


def list_records(data_dir: Path | None = None, limit: int = 50) -> list[dict]:
    """List all saved prediction records (summary only), newest first."""
    data_dir = data_dir or DEFAULT_DATA_DIR
    if not data_dir.exists():
        return []

    records = []
    for filepath in list(data_dir.glob("prediction_*.json")):
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
            records.append({
                "record_id": data.get("record_id"),
                "query": data.get("query"),
                "game_name": data.get("game", {}).get("name"),
                "created_at": data.get("created_at"),
                "sales": data.get("analysis", {}).get("sales"),
            })
        except (json.JSONDecodeError, KeyError):
            continue

    records.sort(key=lambda r: r.get("created_at", ""), reverse=True)
    return records[:limit]


def delete_record(record_id: str, data_dir: Path | None = None) -> bool:
    """Delete a saved prediction record. Returns True if deleted, False if not found."""
    data_dir = data_dir or DEFAULT_DATA_DIR
    if not data_dir.exists():
        return False

    for filepath in list(data_dir.glob("prediction_*.json")):
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
            if data.get("record_id") == record_id:
                filepath.unlink(missing_ok=True)
                gc.collect()
                return True
        except (json.JSONDecodeError, PermissionError):
            continue
    return False

"""Helpers to avoid duplicate scheduled LINE delivery."""

from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo


JST = ZoneInfo("Asia/Tokyo")


def is_scheduled_run() -> bool:
    event_name = os.getenv("GITHUB_EVENT_NAME", "").strip()
    scheduled_dispatch = os.getenv("SCHEDULED_DISPATCH", "").strip().lower()
    return event_name == "schedule" or scheduled_dispatch in {"1", "true", "yes"}


def marker_path(date_slug: str, docs_dir: str = "docs") -> Path:
    return Path(docs_dir) / f".daily_ai_news_sent_{date_slug}"


def already_sent_today(date_slug: str, docs_dir: str = "docs") -> bool:
    return marker_path(date_slug, docs_dir).exists()


def write_sent_marker(
    *,
    date_slug: str,
    delivery_mode: str,
    target_count: int,
    success_count: int,
    failure_count: int,
    docs_dir: str = "docs",
) -> Path:
    path = marker_path(date_slug, docs_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "date": date_slug,
        "sentAtJst": datetime.now(JST).isoformat(timespec="seconds"),
        "deliveryMode": delivery_mode,
        "targetCount": target_count,
        "successCount": success_count,
        "failureCount": failure_count,
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path

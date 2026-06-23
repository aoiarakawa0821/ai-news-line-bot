"""Configuration helpers for the daily AI news app."""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime
from zoneinfo import ZoneInfo


DEFAULT_OPENAI_MODEL = "gpt-5.5-2026-04-23"
JST = ZoneInfo("Asia/Tokyo")


@dataclass(frozen=True)
class AppConfig:
    openai_api_key: str
    line_channel_access_token: str
    line_to_id: str
    line_to_ids: list[str]
    approved_users_endpoint: str
    approved_users_api_key: str
    openai_model: str
    site_base_url: str
    github_repository: str


def _read_required_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(
            f"必須環境変数 {name} が設定されていません。"
            "GitHub ActionsではRepository secretsに登録してください。"
        )
    return value


def infer_site_base_url(github_repository: str) -> str:
    """Infer GitHub Pages URL from owner/repo when SITE_BASE_URL is absent."""
    if not github_repository or "/" not in github_repository:
        return ""
    owner, repo = github_repository.split("/", 1)
    return f"https://{owner}.github.io/{repo}/"


def load_config() -> AppConfig:
    github_repository = os.getenv("GITHUB_REPOSITORY", "").strip()
    site_base_url = os.getenv("SITE_BASE_URL", "").strip() or infer_site_base_url(
        github_repository
    )
    line_to_id = os.getenv("LINE_TO_ID", "").strip()
    line_to_ids = _split_csv(os.getenv("LINE_TO_IDS", ""))
    approved_users_endpoint = os.getenv("APPROVED_USERS_ENDPOINT", "").strip()

    if not approved_users_endpoint and not line_to_ids and not line_to_id:
        raise RuntimeError(
            "送信先が設定されていません。APPROVED_USERS_ENDPOINT、LINE_TO_IDS、"
            "またはLINE_TO_IDのいずれかを設定してください。"
        )

    return AppConfig(
        openai_api_key=_read_required_env("OPENAI_API_KEY"),
        line_channel_access_token=_read_required_env("LINE_CHANNEL_ACCESS_TOKEN"),
        line_to_id=line_to_id,
        line_to_ids=line_to_ids,
        approved_users_endpoint=approved_users_endpoint,
        approved_users_api_key=os.getenv("APPROVED_USERS_API_KEY", "").strip(),
        openai_model=os.getenv("OPENAI_MODEL", DEFAULT_OPENAI_MODEL).strip()
        or DEFAULT_OPENAI_MODEL,
        site_base_url=site_base_url,
        github_repository=github_repository,
    )


def today_jst() -> datetime:
    return datetime.now(JST)


def _split_csv(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]

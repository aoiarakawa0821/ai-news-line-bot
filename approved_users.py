"""Resolve LINE delivery targets from GAS, LINE_TO_IDS, or LINE_TO_ID."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

import requests

from config import AppConfig

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class DeliveryTargets:
    to_ids: list[str]
    mode: str
    warning_message: str = ""


def resolve_delivery_targets(config: AppConfig) -> DeliveryTargets:
    """Resolve recipients without logging userIds or API keys."""
    if config.approved_users_endpoint:
        return _resolve_from_endpoint(config)

    if config.line_to_ids:
        logger.info("LINE_TO_IDSから複数送信先を読み込みました。count=%s", len(config.line_to_ids))
        return DeliveryTargets(to_ids=_deduplicate(config.line_to_ids), mode="LINE_TO_IDS")

    logger.info("LINE_TO_IDから単独送信先を読み込みました。")
    return DeliveryTargets(to_ids=[config.line_to_id], mode="LINE_TO_ID")


def _resolve_from_endpoint(config: AppConfig) -> DeliveryTargets:
    try:
        users = fetch_approved_users(
            endpoint=config.approved_users_endpoint,
            api_key=config.approved_users_api_key,
        )
    except ApprovedUsersError as exc:
        logger.error("approvedユーザー一覧取得に失敗しました。reason=%s", exc.public_reason)
        if config.line_to_id:
            return DeliveryTargets(
                to_ids=[config.line_to_id],
                mode="APPROVED_USERS_ENDPOINT_FALLBACK_ADMIN",
                warning_message=(
                    "【配信先取得エラー】\n"
                    "approvedユーザー一覧取得失敗のため管理者のみに送信します。\n"
                    "GitHub ActionsログとGAS Webhook/API設定を確認してください。\n"
                ),
            )
        return DeliveryTargets(
            to_ids=[],
            mode="APPROVED_USERS_ENDPOINT_FAILED_NO_ADMIN",
            warning_message=(
                "approvedユーザー一覧取得に失敗し、LINE_TO_IDも未設定のため送信先がありません。"
            ),
        )

    user_ids = _deduplicate(
        str(user.get("userId", "")).strip()
        for user in users
        if isinstance(user, dict) and str(user.get("userId", "")).strip()
    )
    logger.info("APPROVED_USERS_ENDPOINTから承認済み送信先を読み込みました。count=%s", len(user_ids))
    return DeliveryTargets(to_ids=user_ids, mode="APPROVED_USERS_ENDPOINT")


def fetch_approved_users(*, endpoint: str, api_key: str, timeout: int = 20) -> list[dict[str, Any]]:
    params = {"action": "approved"}
    if api_key:
        params["key"] = api_key

    try:
        response = requests.get(endpoint, params=params, timeout=timeout)
    except requests.RequestException as exc:
        raise ApprovedUsersError("network_error") from exc

    if response.status_code >= 400:
        raise ApprovedUsersError(f"http_{response.status_code}")

    try:
        data = response.json()
    except ValueError as exc:
        raise ApprovedUsersError("json_parse_error") from exc

    users = data.get("users")
    if not isinstance(users, list):
        raise ApprovedUsersError("missing_users_array")
    return users


class ApprovedUsersError(Exception):
    def __init__(self, public_reason: str) -> None:
        super().__init__(public_reason)
        self.public_reason = public_reason


def _deduplicate(values: list[str] | tuple[str, ...] | Any) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        if value and value not in seen:
            result.append(value)
            seen.add(value)
    return result


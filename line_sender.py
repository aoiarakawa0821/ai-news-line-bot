"""Send LINE push messages with LINE Messaging API."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Iterable

import requests

logger = logging.getLogger(__name__)

LINE_PUSH_URL = "https://api.line.me/v2/bot/message/push"
MAX_LINE_TEXT_LENGTH = 4900


@dataclass(frozen=True)
class SendSummary:
    success_count: int
    failure_count: int


def send_line_message(
    *,
    channel_access_token: str,
    to_id: str,
    message: str,
    timeout: int = 20,
) -> None:
    chunks = split_line_message(message)
    logger.info("LINE Messaging APIへ送信します。messages=%s", len(chunks))

    headers = {
        "Authorization": f"Bearer {channel_access_token}",
        "Content-Type": "application/json",
    }

    for batch in _batched(chunks, 5):
        payload = {
            "to": to_id,
            "messages": [{"type": "text", "text": chunk} for chunk in batch],
        }

        try:
            response = requests.post(
                LINE_PUSH_URL,
                headers=headers,
                json=payload,
                timeout=timeout,
            )
        except requests.RequestException as exc:
            logger.error("LINE送信でネットワークエラーが発生しました。error=%s", exc)
            raise

        if response.status_code >= 400:
            logger.error(
                "LINE送信に失敗しました。status=%s body=%s",
                response.status_code,
                response.text,
            )
            response.raise_for_status()

    logger.info("LINE送信に成功しました。status=%s", response.status_code)


def send_line_message_to_many(
    *,
    channel_access_token: str,
    to_ids: list[str],
    message: str,
    timeout: int = 20,
) -> SendSummary:
    success_count = 0
    failure_count = 0

    for to_id in to_ids:
        try:
            send_line_message(
                channel_access_token=channel_access_token,
                to_id=to_id,
                message=message,
                timeout=timeout,
            )
            success_count += 1
        except requests.RequestException:
            failure_count += 1
            logger.exception("LINE送信に失敗しました。処理は続行します。")

    logger.info("LINE一斉送信が完了しました。success=%s failure=%s", success_count, failure_count)
    return SendSummary(success_count=success_count, failure_count=failure_count)


def split_line_message(message: str) -> list[str]:
    """Split long LINE text into multiple messages without dropping content."""
    message = message.strip()
    if len(message) <= MAX_LINE_TEXT_LENGTH:
        return [message]

    detail = _extract_detail_line(message)
    body = _remove_detail_line(message, detail) if detail else message
    chunks = list(_split_by_length(body, MAX_LINE_TEXT_LENGTH))
    if detail and chunks and detail not in chunks[0]:
        chunks = _append_detail_to_first_chunk(chunks, detail)
    return _deduplicate_preserving_order(chunks)


def _append_detail_to_first_chunk(chunks: list[str], detail: str) -> list[str]:
    first = chunks[0].rstrip()
    suffix = f"\n\n{detail}"
    first_budget = MAX_LINE_TEXT_LENGTH - len(suffix)
    if first_budget <= 0:
        return chunks

    overflow = ""
    if len(first) > first_budget:
        overflow = first[first_budget:].lstrip()
        first = first[:first_budget].rstrip()

    result = [f"{first}{suffix}".strip()]
    if overflow:
        result.extend(_split_by_length(overflow, MAX_LINE_TEXT_LENGTH))
    result.extend(chunks[1:])
    return result


def _extract_detail_line(message: str) -> str:
    for line in message.splitlines():
        if "詳細版" in line and ("http://" in line or "https://" in line):
            return line.strip()
    index = message.find("詳細版")
    if index < 0:
        return ""
    return message[index : index + 300].strip()


def _remove_detail_line(message: str, detail: str) -> str:
    lines = [line for line in message.splitlines() if line.strip() != detail]
    return "\n".join(lines).strip()


def _split_by_length(text: str, max_length: int) -> Iterable[str]:
    current: list[str] = []
    current_len = 0
    for paragraph in text.splitlines():
        next_len = len(paragraph) + 1
        if current and current_len + next_len > max_length:
            yield "\n".join(current).strip()
            current = []
            current_len = 0
        if len(paragraph) > max_length:
            for index in range(0, len(paragraph), max_length):
                yield paragraph[index : index + max_length]
        else:
            current.append(paragraph)
            current_len += next_len
    if current:
        yield "\n".join(current).strip()


def _deduplicate_preserving_order(chunks: list[str]) -> list[str]:
    result: list[str] = []
    for chunk in chunks:
        normalized = chunk.strip()
        if normalized and normalized not in result:
            result.append(normalized)
    return result


def _batched(items: list[str], size: int) -> Iterable[list[str]]:
    for index in range(0, len(items), size):
        yield items[index : index + size]

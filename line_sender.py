"""Send LINE push messages with LINE Messaging API."""

from __future__ import annotations

import logging
from typing import Iterable

import requests

logger = logging.getLogger(__name__)

LINE_PUSH_URL = "https://api.line.me/v2/bot/message/push"
MAX_LINE_TEXT_LENGTH = 4900


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


def split_line_message(message: str) -> list[str]:
    """Split long LINE text into multiple messages without dropping content."""
    message = message.strip()
    if len(message) <= MAX_LINE_TEXT_LENGTH:
        return [message]

    first = _build_first_message(message)
    remaining = message
    for marker in ("【今日読むべき記事】", "今日読むべき記事", "詳細版:"):
        index = remaining.find(marker)
        if index > 0:
            remaining = remaining[index:]
            break

    chunks = [first]
    chunks.extend(_split_by_length(remaining, MAX_LINE_TEXT_LENGTH))
    return _deduplicate_preserving_order(chunks)


def _build_first_message(message: str) -> str:
    detail = _extract_detail_line(message)
    reserved = len(detail) + 2 if detail else 0
    body_budget = max(1000, MAX_LINE_TEXT_LENGTH - reserved)

    conclusion = _extract_section(message, start="【今日の結論】", end="【重要ニュース】")
    important = _extract_section(message, start="【重要ニュース】", end="【今日読むべき記事】")
    first = "\n\n".join(part for part in [conclusion, important] if part).strip()
    if not first:
        first = message[:body_budget]
    if len(first) > body_budget:
        first = first[: body_budget - 1].rstrip() + "…"
    if detail and detail not in first:
        first = f"{first}\n\n{detail}".strip()
    return first[:MAX_LINE_TEXT_LENGTH]


def _extract_section(message: str, *, start: str, end: str | None) -> str:
    start_index = message.find(start)
    if start_index < 0:
        return ""
    end_index = len(message) if end is None else message.find(end, start_index + len(start))
    if end_index < 0:
        end_index = len(message)
    return message[start_index:end_index].strip()


def _extract_detail_line(message: str) -> str:
    for line in message.splitlines():
        if "詳細版" in line and ("http://" in line or "https://" in line):
            return line.strip()
    index = message.find("詳細版")
    if index < 0:
        return ""
    return message[index : index + 300].strip()


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

"""Generate an AI news briefing with OpenAI Responses API and web search."""

from __future__ import annotations

import json
import logging
import re
import time
from dataclasses import dataclass
from typing import Any

from openai import APIConnectionError, APIError, OpenAI, RateLimitError

logger = logging.getLogger(__name__)


BRIEFING_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": [
        "date_jst",
        "line_message",
        "detailed_markdown",
        "sources",
        "must_read",
        "deep_dive_candidates",
    ],
    "properties": {
        "date_jst": {"type": "string"},
        "line_message": {"type": "string"},
        "detailed_markdown": {"type": "string"},
        "sources": {
            "type": "array",
            "items": {"type": "string"},
        },
        "must_read": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["title", "reason", "url"],
                "properties": {
                    "title": {"type": "string"},
                    "reason": {"type": "string"},
                    "url": {"type": "string"},
                },
            },
        },
        "deep_dive_candidates": {
            "type": "array",
            "items": {"type": "string"},
        },
    },
}


@dataclass(frozen=True)
class Briefing:
    date_jst: str
    line_message: str
    detailed_markdown: str
    sources: list[str]
    must_read: list[dict[str, str]]
    deep_dive_candidates: list[str]


def generate_news_briefing(
    *,
    api_key: str,
    model: str,
    date_jst: str,
    detail_url: str,
    max_attempts: int = 3,
) -> Briefing:
    """Generate a briefing. Retries JSON/API failures and returns a safe fallback."""
    client = OpenAI(api_key=api_key)
    last_error: Exception | None = None

    for attempt in range(1, max_attempts + 1):
        try:
            logger.info("OpenAI Responses APIでニュース生成を開始します。attempt=%s", attempt)
            response = client.responses.create(
                model=model,
                input=_build_prompt(date_jst=date_jst, detail_url=detail_url),
                tools=[{"type": "web_search"}],
                text={
                    "format": {
                        "type": "json_schema",
                        "name": "daily_ai_news_briefing",
                        "schema": BRIEFING_SCHEMA,
                        "strict": True,
                    }
                },
            )
            raw_text = _response_text(response)
            parsed = _parse_json(raw_text)
            briefing = _briefing_from_dict(parsed, date_jst=date_jst, detail_url=detail_url)
            logger.info("OpenAIニュース生成に成功しました。sources=%s", len(briefing.sources))
            return briefing
        except (json.JSONDecodeError, ValueError) as exc:
            last_error = exc
            logger.warning("OpenAIのJSON解析に失敗しました。attempt=%s error=%s", attempt, exc)
        except RateLimitError as exc:
            last_error = exc
            logger.warning("OpenAI APIのレート制限を受けました。attempt=%s", attempt)
        except (APIConnectionError, APIError) as exc:
            last_error = exc
            logger.warning("OpenAI API呼び出しに失敗しました。attempt=%s error=%s", attempt, exc)

        if attempt < max_attempts:
            time.sleep(2 * attempt)

    logger.error("OpenAIニュース生成に失敗したため、安全なフォールバックを生成します。")
    return _fallback_briefing(date_jst=date_jst, detail_url=detail_url, error=last_error)


def _build_prompt(*, date_jst: str, detail_url: str) -> str:
    return f"""
あなたは日本語のAIニュース編集者です。現在日時は {date_jst} JST です。
OpenAI Responses APIのweb_search toolで、過去24時間を優先してAIニュースを調査してください。

目的:
毎朝7:00 JSTに、Apple / Google / OpenAI / Anthropic / Microsoft / NVIDIA /
AI搭載端末・OS に関するニュースを収集し、日本語で要約する。

優先順位:
1. Apple関連
2. 技術的に面白いニュース
3. OS・端末にAIが統合されるニュース
4. OpenAI / Anthropic / Google / Microsoft のモデル・エージェント・プロダクト更新
5. NVIDIAなどAI実行基盤・AI PC関連

収集対象キーワード:
Apple, Apple Intelligence, Siri AI, iOS, iPadOS, macOS, visionOS,
AI-enabled device, AI-enabled OS, Google, Gemini, Android AI, Chrome AI,
OpenAI, ChatGPT, Codex, Anthropic, Claude, Microsoft, Copilot, M365 Copilot,
Windows AI, Azure AI, NVIDIA, AI PC, local AI, on-device AI

必ず守る条件:
- 日本語記事と無料で読める記事を優先する。
- 英語記事は、公式情報、一次情報、日本語記事がない場合、信頼性が高い場合だけ使う。
- 株価、決算、投資家向け、アナリスト評価、目標株価、M&A観測中心の記事は除外する。
- 噂はBloomberg, The Verge, 9to5Mac, MacRumorsなど信頼できる媒体に限る。
- 噂は必ず「未確認情報」または「噂」と明記する。
- Bloombergなど有料記事は、無料で確認できる信頼性のある二次情報がある場合だけ扱う。
- 内容が薄い転載記事や広告記事は除外する。
- ニュースが少ない場合は水増しせず「本日は条件に合う重要ニュースが少なめです」と明記する。
- kintone、社内業務改善、業務フロー設計、WWDC資料作成向け観点は入れない。

LINE短縮版 line_message:
- 詳細版全文を入れない。
- 見出しは必ず「【今日の結論】」「【重要ニュース】」「【今日読むべき記事】」「詳細版: URL」にする。
- 「今日の結論」「重要ニュース3〜5本」「今日読むべき記事1〜3本」「詳細版リンク」を含める。
- 詳細版リンクは {detail_url} を使う。
- 原則1通で読める長さにする。

詳細版 detailed_markdown:
以下の構成を日本語Markdownで作る。

# AIニュース詳細版｜YYYY年MM月DD日 7:00 JST

## 今日の結論
- 今日の全体傾向を3〜5行で要約
- 特に重要なニュースを1〜3件

## Apple
各ニュースに、見出し、3行要約、公開タイミング、重要度、信頼度、
自分向けの意味、解釈・評価、今後の見通し、ソースURLを含める。

## Google
同上。

## Other AI
OpenAI、Anthropic、Microsoft、NVIDIA、AI搭載端末・OSなどをまとめる。同上。

## 今日読むべき記事
1〜3本。読むべき理由とURLを示す。

## 深掘り候補
3〜5件。

返答はJSONだけにしてください。前後に説明文やMarkdownコードフェンスを書かないでください。
""".strip()


def _response_text(response: Any) -> str:
    output_text = getattr(response, "output_text", None)
    if output_text:
        return str(output_text)

    chunks: list[str] = []
    for item in getattr(response, "output", []) or []:
        for content in getattr(item, "content", []) or []:
            text = getattr(content, "text", None)
            if text:
                chunks.append(str(text))
    return "\n".join(chunks)


def _parse_json(raw_text: str) -> dict[str, Any]:
    if not raw_text.strip():
        raise ValueError("OpenAI response text is empty")
    try:
        return json.loads(raw_text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", raw_text, flags=re.DOTALL)
        if not match:
            raise
        return json.loads(match.group(0))


def _briefing_from_dict(
    data: dict[str, Any],
    *,
    date_jst: str,
    detail_url: str,
) -> Briefing:
    line_message = str(data.get("line_message", "")).strip()
    detailed_markdown = str(data.get("detailed_markdown", "")).strip()
    if detail_url and detail_url not in line_message:
        line_message = f"{line_message}\n\n詳細版: {detail_url}".strip()

    if not line_message or not detailed_markdown:
        raise ValueError("line_messageまたはdetailed_markdownが空です")

    return Briefing(
        date_jst=str(data.get("date_jst") or date_jst),
        line_message=line_message,
        detailed_markdown=detailed_markdown,
        sources=[str(url) for url in data.get("sources", []) if str(url).strip()],
        must_read=[
            {
                "title": str(item.get("title", "")),
                "reason": str(item.get("reason", "")),
                "url": str(item.get("url", "")),
            }
            for item in data.get("must_read", [])
            if isinstance(item, dict)
        ],
        deep_dive_candidates=[
            str(item) for item in data.get("deep_dive_candidates", []) if str(item).strip()
        ],
    )


def _fallback_briefing(
    *,
    date_jst: str,
    detail_url: str,
    error: Exception | None,
) -> Briefing:
    error_message = type(error).__name__ if error else "UnknownError"
    line_message = (
        "【今日の結論】\n"
        "本日はAIニュース生成に失敗しました。GitHub Actionsのログを確認してください。\n\n"
        "【重要ニュース】\n"
        "本日は条件に合う重要ニュースが少なめです。\n\n"
        f"詳細版: {detail_url}"
    )
    detailed_markdown = f"""# AIニュース詳細版｜{date_jst} JST

## 今日の結論
- 本日はOpenAI APIまたはJSON解析でエラーが発生したため、通常のニュース収集結果を生成できませんでした。
- GitHub ActionsのログでOpenAI API、レート制限、ネットワークエラー、JSONパース失敗を確認してください。
- 本日は条件に合う重要ニュースが少なめです。

## Apple
- 生成失敗のため掲載なし。

## Google
- 生成失敗のため掲載なし。

## Other AI
- 生成失敗のため掲載なし。

## 今日読むべき記事
- 生成失敗のため掲載なし。

## 深掘り候補
- OpenAI APIの実行ログ確認
- GitHub Secretsの設定確認
- LINE Messaging APIの送信ログ確認

## エラー種別
{error_message}
"""
    return Briefing(
        date_jst=date_jst,
        line_message=line_message,
        detailed_markdown=detailed_markdown,
        sources=[],
        must_read=[],
        deep_dive_candidates=[
            "OpenAI APIの実行ログ確認",
            "GitHub Secretsの設定確認",
            "LINE Messaging APIの送信ログ確認",
        ],
    )

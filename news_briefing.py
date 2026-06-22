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
        "overall_summary",
        "news_items",
        "line_message",
        "detailed_markdown",
        "sources",
        "must_read",
        "deep_dive_candidates",
        "editor_note",
    ],
    "properties": {
        "date_jst": {"type": "string"},
        "overall_summary": {
            "type": "object",
            "additionalProperties": False,
            "required": ["conclusion", "key_points"],
            "properties": {
                "conclusion": {"type": "string"},
                "key_points": {
                    "type": "array",
                    "items": {"type": "string"},
                },
            },
        },
        "news_items": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": [
                    "category",
                    "title",
                    "line_summary",
                    "summary_points",
                    "published_timing",
                    "importance",
                    "reliability",
                    "user_meaning",
                    "analysis",
                    "outlook",
                    "source_url",
                ],
                "properties": {
                    "category": {"type": "string"},
                    "title": {"type": "string"},
                    "line_summary": {"type": "string"},
                    "summary_points": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                    "published_timing": {"type": "string"},
                    "importance": {"type": "string"},
                    "reliability": {"type": "string"},
                    "user_meaning": {"type": "string"},
                    "analysis": {"type": "string"},
                    "outlook": {"type": "string"},
                    "source_url": {"type": "string"},
                },
            },
        },
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
        "editor_note": {"type": "string"},
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
    is_fallback: bool = False


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
あなたは日本語のAI・ITニュース編集者です。現在日時は {date_jst} JST です。
OpenAI Responses APIのweb_search toolで、過去24時間を優先してAI・IT技術ニュースを調査してください。

目的:
毎朝7:00 JSTに、AI技術・IT技術・主要テック企業・AI搭載端末・OS・開発者向けツール・AI実行基盤に関する重要ニュースを収集し、日本語で要約する。

対象範囲:
- AIモデル、生成AI、エージェント、AIアプリ、開発者向けAIツール
- OpenAI / Anthropic / Google / Microsoft / Meta / xAI / Perplexity などのAI関連ニュース
- Apple / Google / Microsoft などのOS・端末・プラットフォームへのAI統合
- NVIDIA / AMD / Intel / Qualcomm / Arm などのAI半導体・AI実行基盤
- AI PC、オンデバイスAI、ローカルAI、エッジAI、AI搭載スマートフォン
- クラウドAI、API、開発基盤、エージェント基盤、AI検索
- セキュリティ、プライバシー、著作権、規制など、AI利用に影響する重要トピック
- その他、AI・IT技術の今後に影響しそうなニュース

優先順位:
1. 技術的・社会的インパクトが大きいAI・ITニュース
2. モデル、エージェント、開発者向けツール、AIアプリ、AI検索の重要アップデート
3. OS・端末・ブラウザ・クラウドにAIが統合されるニュース
4. OpenAI / Anthropic / Google / Microsoft / Meta / Apple / NVIDIA など主要企業の重要発表
5. AI半導体、AI PC、オンデバイスAI、ローカルAIなど実行基盤のニュース
6. Apple関連ニュースは重要なら扱うが、必ず最優先にはしない

収集対象キーワード:
AI, generative AI, AI agent, AI assistant, AI search, AI browser,
OpenAI, ChatGPT, Codex, Anthropic, Claude, Google, Gemini, DeepMind,
Microsoft, Copilot, M365 Copilot, Windows AI, Azure AI,
Apple, Apple Intelligence, Siri, iOS, iPadOS, macOS, visionOS,
Meta AI, xAI, Grok, Perplexity, AI startup,
NVIDIA, CUDA, GPU, AMD, Intel, Qualcomm, Arm, AI chip,
AI PC, on-device AI, local AI, edge AI, AI-enabled OS, AI-enabled device,
developer tools, coding agent, cloud AI, AI infrastructure,
privacy, security, copyright, regulation

必ず守る条件:
- 過去24時間以内の記事・発表を最優先する。
- 日本語記事と無料で読める記事を優先する。
- 英語記事は、公式情報、一次情報、日本語記事がない場合、信頼性が高い場合だけ使う。
- 公式ブログ、公式発表、開発者向けドキュメント、一次情報を優先する。
- 大手報道・専門メディアは信頼度を明記して使う。
- 株価、決算、投資家向け、アナリスト評価、目標株価、M&A観測中心の記事は除外する。
- 噂はBloomberg, The Verge, 9to5Mac, MacRumorsなど信頼できる媒体に限る。
- 噂は必ず「未確認情報」または「噂」と明記する。
- Bloombergなど有料記事は、無料で確認できる信頼性のある二次情報がある場合だけ扱う。
- 内容が薄い転載記事、広告記事、SEO目的の記事は除外する。
- ニュースが少ない場合は水増しせず「本日は条件に合う重要ニュースが少なめです」と明記する。
- kintone、社内業務改善、業務フロー設計、WWDC資料作成向け観点は入れない。
- 事実と推測を混ぜない。推測や見通しは「見通し」「解釈」と明記する。
- 各ニュースには、可能な限りソースURLを含める。
- 同じニュースの重複記事はまとめ、最も信頼できるソースを使う。

出力の作り方:
1. まず `news_items` を作る。これがLINE短縮版と詳細版の唯一の正本です。
2. `news_items` は重要度・新しさ・技術的/社会的インパクトを総合して、重要な順に並べる。
3. LINE短縮版 `line_message` と詳細版 `detailed_markdown` は、必ず `news_items` と同じニュース、同じ順序、同じ重要度、同じ信頼度、同じURLを使う。
4. 詳細版でカテゴリ別に並べ替えない。Apple / Google / OpenAI などの分類は `category` と見出し内で示し、本文の順序は `news_items` の順序を保つ。
5. Apple関連は重要なら扱うが、必ず最優先にはしない。
6. ニュースが少ない場合は水増しせず、`news_items` を3本未満にしてよい。その場合は `editor_note` とLINEの補足に「本日は条件に合う重要ニュースが少なめです」と書く。

news_items の各項目:
- category: 例「AIモデル」「AIエージェント」「OS・端末AI」「AI検索」「開発者ツール」「AI半導体」「セキュリティ・規制」「Apple」「Google」「OpenAI」「Anthropic」「Microsoft」「NVIDIA」など。
- title: ニュース見出し。毎日読みやすい短い見出しにする。
- line_summary: LINE用の概要。2〜3文で、何が起きたかが分かる長さにする。
- summary_points: 詳細版用の3行要約。必ず3件を目安にする。
- published_timing: 「過去24時間以内」「過去48時間以内」「公式発表日: YYYY-MM-DD」など、古いニュースを最新扱いしない書き方にする。
- importance: 「高」「中」「低」のいずれか。
- reliability: 「公式」「大手報道」「専門メディア」「噂」のいずれか。噂の場合はtitleまたはanalysisに必ず「噂」または「未確認情報」と書く。
- user_meaning: 個人の関心、技術トレンド、製品体験、主要企業動向の理解として何を意味するかを書く。kintone、社内業務改善、業務フロー設計、WWDC資料作成向け観点は入れない。
- analysis: 解釈・評価。事実と推測を分けて書く。
- outlook: 今後の見通し。推測は「見通し」と分かるように書く。
- source_url: 無料で確認できるソースURL。URLがないニュースは原則採用しない。

overall_summary:
- conclusion: 今日の全体傾向を2〜4文で説明する。単なる箇条書きではなく、今日のAI・ITニュース全体が何を示しているのかを書く。
- key_points: 詳細版の「今日の結論」に使う要点を3〜5件。

must_read:
- 1〜3本。
- 原則として `news_items` に含めたニュースのURLから選ぶ。
- LINE短縮版と詳細版で同じ順序にする。

deep_dive_candidates:
- 3〜5件。
- 今後追うべき理由が分かる短い文にする。

editor_note:
- 今日のニュースの読み方を1〜3文で書く。
- ニュースが少ない日、噂が多い日、公式発表が少ない日などはここに明記する。
- 特に補足がなければ「特になし」と書く。

line_message:
必ず次の固定テンプレートで作る。見出し名、順番、括弧を変えない。

【今日の結論】
{{overall_summary.conclusion と同じ内容。2〜4文。}}

【重要ニュース】

1. {{news_items[0].category}}｜{{news_items[0].title}}
    概要：{{news_items[0].line_summary}}
    重要度：{{news_items[0].importance}}
    信頼度：{{news_items[0].reliability}}
    意味：{{news_items[0].user_meaning}}
2. {{news_items[1].category}}｜{{news_items[1].title}}
    概要：{{news_items[1].line_summary}}
    重要度：{{news_items[1].importance}}
    信頼度：{{news_items[1].reliability}}
    意味：{{news_items[1].user_meaning}}

{{news_items の件数に応じて同じ形式で続ける。最大5本。不要なら出さない。}}

【今日読むべき記事】

1. {{must_read[0].title}}
    理由：{{must_read[0].reason}}
    URL：{{must_read[0].url}}

{{must_read の件数に応じて同じ形式で続ける。最大3本。不要なら「本日は該当なし」と書く。}}

【補足】
{{editor_note}}

詳細版: {detail_url}

detailed_markdown:
必ず次の固定テンプレートで作る。LINE短縮版の重要ニュースと同じ順序にする。

# AIニュース詳細版｜YYYY年MM月DD日 7:00 JST

## 今日の結論
- {{overall_summary.key_points[0]}}
- {{overall_summary.key_points[1]}}
- {{overall_summary.key_points[2]}}

## 重要ニュース（LINEと同じ順序）

### 1. {{news_items[0].category}}｜{{news_items[0].title}}
- 3行要約:
  - {{news_items[0].summary_points[0]}}
  - {{news_items[0].summary_points[1]}}
  - {{news_items[0].summary_points[2]}}
- 公開タイミング: {{news_items[0].published_timing}}
- 重要度: {{news_items[0].importance}}
- 信頼度: {{news_items[0].reliability}}
- 自分向けの意味: {{news_items[0].user_meaning}}
- 解釈・評価: {{news_items[0].analysis}}
- 今後の見通し: {{news_items[0].outlook}}
- ソースURL: {{news_items[0].source_url}}

{{news_items の件数に応じて同じ形式で続ける。}}

## 今日読むべき記事
1. {{must_read[0].title}}
   - 理由: {{must_read[0].reason}}
   - URL: {{must_read[0].url}}

## 深掘り候補
- {{deep_dive_candidates[0]}}
- {{deep_dive_candidates[1]}}
- {{deep_dive_candidates[2]}}

## 補足
{{editor_note}}

重要な品質ルール:
- `news_items` の順序を、LINE短縮版・詳細版・must_read候補の基準にする。
- LINE短縮版と詳細版で、タイトル、重要度、信頼度、URLを変えない。
- 詳細版だけに重要ニュースを追加したり、LINEだけに重要ニュースを追加したりしない。
- 詳細版の文章量はLINEより長くしてよいが、ニュースの選定と順序は変えない。
- Markdownの表は使わない。
- 返答JSONには必ず date_jst, overall_summary, news_items, line_message, detailed_markdown, sources, must_read, deep_dive_candidates, editor_note を含める。

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
    news_items = _normalize_news_items(data.get("news_items", []))
    overall_summary = _normalize_overall_summary(data.get("overall_summary", {}), news_items)
    must_read = _normalize_must_read(data.get("must_read", []), news_items)
    deep_dive_candidates = _clean_string_list(data.get("deep_dive_candidates", []), limit=5)
    if not deep_dive_candidates:
        deep_dive_candidates = [
            "AIモデルとエージェント機能の次の更新",
            "OS・端末へのオンデバイスAI統合",
            "AI検索と開発者向けツールの実用化",
        ]
    editor_note = _clean_text(data.get("editor_note")) or "特になし"

    line_message = _render_line_message(
        overall_summary=overall_summary,
        news_items=news_items,
        must_read=must_read,
        editor_note=editor_note,
        detail_url=detail_url,
    )
    detailed_markdown = _render_detailed_markdown(
        date_jst=date_jst,
        overall_summary=overall_summary,
        news_items=news_items,
        must_read=must_read,
        deep_dive_candidates=deep_dive_candidates,
        editor_note=editor_note,
    )
    sources = _deduplicate_strings(
        [str(url) for url in data.get("sources", []) if str(url).strip()]
        + [item["source_url"] for item in news_items]
    )

    return Briefing(
        date_jst=str(data.get("date_jst") or date_jst),
        line_message=line_message,
        detailed_markdown=detailed_markdown,
        sources=sources,
        must_read=must_read,
        deep_dive_candidates=deep_dive_candidates,
        is_fallback=False,
    )


def _normalize_news_items(raw_items: Any) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    if not isinstance(raw_items, list):
        return items

    for raw in raw_items[:5]:
        if not isinstance(raw, dict):
            continue
        title = _clean_text(raw.get("title"))
        source_url = _clean_text(raw.get("source_url"))
        if not title or not source_url:
            continue

        line_summary = _clean_text(raw.get("line_summary")) or "詳細はソース記事を確認してください。"
        summary_points = _clean_string_list(raw.get("summary_points", []), limit=3)
        while len(summary_points) < 3:
            summary_points.append(line_summary)

        items.append(
            {
                "category": _clean_text(raw.get("category")) or "AI・IT",
                "title": title,
                "line_summary": line_summary,
                "summary_points": summary_points[:3],
                "published_timing": _clean_text(raw.get("published_timing")) or "公開タイミング未確認",
                "importance": _normalize_choice(raw.get("importance"), {"高", "中", "低"}, "中"),
                "reliability": _normalize_choice(
                    raw.get("reliability"),
                    {"公式", "大手報道", "専門メディア", "噂"},
                    "専門メディア",
                ),
                "user_meaning": _clean_text(raw.get("user_meaning"))
                or "AI・ITの流れを把握するうえで確認しておきたいニュースです。",
                "analysis": _clean_text(raw.get("analysis")) or "現時点では追加の評価材料を確認中です。",
                "outlook": _clean_text(raw.get("outlook")) or "今後の公式発表や続報を確認します。",
                "source_url": source_url,
            }
        )
    return items


def _normalize_overall_summary(raw: Any, news_items: list[dict[str, Any]]) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raw = {}
    conclusion = _clean_text(raw.get("conclusion"))
    if not conclusion:
        conclusion = (
            "本日は条件に合う重要ニュースが少なめです。"
            if not news_items
            else "今日のAI・ITニュースは、重要な技術更新を中心に確認する日です。"
        )
    key_points = _clean_string_list(raw.get("key_points", []), limit=5)
    if not key_points:
        key_points = [conclusion]
    return {"conclusion": conclusion, "key_points": key_points}


def _normalize_must_read(
    raw_items: Any,
    news_items: list[dict[str, Any]],
) -> list[dict[str, str]]:
    url_to_item = {item["source_url"]: item for item in news_items}
    selected_urls: set[str] = set()
    raw_by_url: dict[str, dict[str, str]] = {}

    if isinstance(raw_items, list):
        for raw in raw_items:
            if not isinstance(raw, dict):
                continue
            url = _clean_text(raw.get("url"))
            if not url or url not in url_to_item:
                continue
            selected_urls.add(url)
            raw_by_url[url] = {
                "title": _clean_text(raw.get("title")),
                "reason": _clean_text(raw.get("reason")),
                "url": url,
            }

    if not selected_urls:
        selected_urls = {item["source_url"] for item in news_items[: min(3, len(news_items))]}

    result: list[dict[str, str]] = []
    for item in news_items:
        url = item["source_url"]
        if url not in selected_urls:
            continue
        raw = raw_by_url.get(url, {})
        result.append(
            {
                "title": item["title"],
                "reason": raw.get("reason")
                or "今日の重要ニュース全体を把握する起点になるため。",
                "url": url,
            }
        )
        if len(result) >= 3:
            break
    return result


def _render_line_message(
    *,
    overall_summary: dict[str, Any],
    news_items: list[dict[str, Any]],
    must_read: list[dict[str, str]],
    editor_note: str,
    detail_url: str,
) -> str:
    lines: list[str] = [
        "【今日の結論】",
        str(overall_summary["conclusion"]),
        "",
        "【重要ニュース】",
        "",
    ]

    if news_items:
        for index, item in enumerate(news_items, start=1):
            lines.extend(
                [
                    f"{index}. {item['category']}｜{item['title']}",
                    f"    概要：{item['line_summary']}",
                    f"    重要度：{item['importance']}",
                    f"    信頼度：{item['reliability']}",
                    f"    意味：{item['user_meaning']}",
                ]
            )
    else:
        lines.append("本日は条件に合う重要ニュースが少なめです。")

    lines.extend(["", "【今日読むべき記事】", ""])
    if must_read:
        for index, item in enumerate(must_read, start=1):
            lines.extend(
                [
                    f"{index}. {item['title']}",
                    f"    理由：{item['reason']}",
                    f"    URL：{item['url']}",
                ]
            )
    else:
        lines.append("本日は該当なし。")

    lines.extend(["", "【補足】", editor_note or "特になし", "", f"詳細版: {detail_url}"])
    return "\n".join(lines).strip()


def _render_detailed_markdown(
    *,
    date_jst: str,
    overall_summary: dict[str, Any],
    news_items: list[dict[str, Any]],
    must_read: list[dict[str, str]],
    deep_dive_candidates: list[str],
    editor_note: str,
) -> str:
    lines: list[str] = [
        f"# AIニュース詳細版｜{_detail_title_date(date_jst)}",
        "",
        "## 今日の結論",
    ]
    lines.extend(f"- {point}" for point in overall_summary["key_points"])
    lines.extend(["", "## 重要ニュース（LINEと同じ順序）", ""])

    if news_items:
        for index, item in enumerate(news_items, start=1):
            lines.extend(
                [
                    f"### {index}. {item['category']}｜{item['title']}",
                    "- 3行要約:",
                ]
            )
            lines.extend(f"  - {point}" for point in item["summary_points"])
            lines.extend(
                [
                    f"- 公開タイミング: {item['published_timing']}",
                    f"- 重要度: {item['importance']}",
                    f"- 信頼度: {item['reliability']}",
                    f"- 自分向けの意味: {item['user_meaning']}",
                    f"- 解釈・評価: {item['analysis']}",
                    f"- 今後の見通し: {item['outlook']}",
                    f"- ソースURL: {item['source_url']}",
                    "",
                ]
            )
    else:
        lines.extend(["本日は条件に合う重要ニュースが少なめです。", ""])

    lines.extend(["## 今日読むべき記事"])
    if must_read:
        for index, item in enumerate(must_read, start=1):
            lines.extend(
                [
                    f"{index}. {item['title']}",
                    f"   - 理由: {item['reason']}",
                    f"   - URL: {item['url']}",
                ]
            )
    else:
        lines.append("- 本日は該当なし。")

    lines.extend(["", "## 深掘り候補"])
    lines.extend(f"- {item}" for item in deep_dive_candidates)
    lines.extend(["", "## 補足", editor_note or "特になし", ""])
    return "\n".join(lines).strip() + "\n"


def _detail_title_date(date_jst: str) -> str:
    date_part = str(date_jst).split()[0] if date_jst else ""
    return f"{date_part} 7:00 JST" if date_part else "7:00 JST"


def _clean_text(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _clean_string_list(value: Any, *, limit: int) -> list[str]:
    if not isinstance(value, list):
        return []
    return [_clean_text(item) for item in value if _clean_text(item)][:limit]


def _normalize_choice(value: Any, allowed: set[str], default: str) -> str:
    text = _clean_text(value)
    return text if text in allowed else default


def _deduplicate_strings(values: list[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = _clean_text(value)
        if text and text not in seen:
            result.append(text)
            seen.add(text)
    return result


def _fallback_briefing(
    *,
    date_jst: str,
    detail_url: str,
    error: Exception | None,
) -> Briefing:
    error_message = type(error).__name__ if error else "UnknownError"
    line_message = (
        "【今日の結論】\n"
        "本日はAIニュース生成に失敗しました。GitHub Actionsのログを確認してください。"
        "通常配信としては扱わず、バックアップ実行で再試行します。\n\n"
        "【重要ニュース】\n"
        "本日は条件に合う重要ニュースが少なめです。\n\n"
        "【今日読むべき記事】\n"
        "本日は該当なし。\n\n"
        "【補足】\n"
        f"エラー種別: {error_message}\n\n"
        f"詳細版: {detail_url}"
    )
    detailed_markdown = f"""# AIニュース詳細版｜{_detail_title_date(date_jst)}

## 今日の結論
- 本日はOpenAI APIまたはJSON解析でエラーが発生したため、通常のニュース収集結果を生成できませんでした。
- GitHub ActionsのログでOpenAI API、レート制限、ネットワークエラー、JSONパース失敗を確認してください。
- 本日は条件に合う重要ニュースが少なめです。

## 重要ニュース（LINEと同じ順序）
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
        is_fallback=True,
    )

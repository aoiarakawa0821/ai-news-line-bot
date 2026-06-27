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
        "selection_basis",
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
        "selection_basis": {
            "type": "array",
            "items": {"type": "string"},
        },
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
                    "selection_reason",
                    "long_term_significance",
                    "user_meaning",
                    "analysis",
                    "outlook",
                    "source_url",
                ],
                "properties": {
                    "category": {
                        "type": "string",
                        "enum": ["Apple", "Google", "Microsoft", "Meta/Amazon", "Other AI"],
                    },
                    "title": {"type": "string"},
                    "line_summary": {"type": "string"},
                    "summary_points": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                    "published_timing": {"type": "string"},
                    "importance": {"type": "string", "enum": ["高", "中", "低"]},
                    "reliability": {
                        "type": "string",
                        "enum": ["公式", "大手報道", "専門メディア", "噂", "有料記事・確認済み"],
                    },
                    "selection_reason": {"type": "string"},
                    "long_term_significance": {"type": "string"},
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
OpenAI Responses APIのweb_search toolで、AI・IT技術ニュースを調査し、日本語で編集してください。

最重要方針:
- ソース記事は、7:00 JSTのブリーフィング時点から過去24時間以内に公開された記事・公式発表だけに厳密に限定する。
- 24時間より古い記事を、背景説明や続報のソース記事として採用しない。
- 古い出来事が重要な場合は、過去24時間以内の記事本文の中で参照されている場合だけ触れてよい。その場合も、ソース記事自体が新しいことを明記する。
- 24時間以内の記事の中でも、通知直前に公開された新しい記事を優先する。
- 同じ日に複数回実行すると、新しい記事の出現で結果が変わり得る。その場合は実行時点で取得できる最新記事を優先し、補足でその可能性に触れる。

対象企業:
- Apple
- Google
- Microsoft
- Meta
- Amazon
- OpenAI
- Anthropic
- NVIDIA

上記8社は、デフォルトでは同じ重要度の対象企業として扱う。Appleを常に最優先にしない。

対象テーマ:
- AI搭載端末、AI搭載OS、OS・ブラウザ・アプリへのAI統合
- AIアシスタント、AIエージェント、AI検索、AIブラウザ
- モデル発表、モデル利用制限、モデルアクセス、API、開発者向けAIツール、AIコーディング
- サブスクリプション、製品価格変更、提供地域、提供開始・終了、利用条件変更
- AIハードウェア要件、チップロードマップ、GPU、メモリ、ストレージ、AI PC
- AIインフラ、データセンター、電力、冷却、クラウドAI
- セキュリティ、プライバシー、著作権、規制
- その他、AI・ITの中長期的な製品体験やプラットフォーム戦略に影響するニュース

選定Tier:
Tier 1:
- Apple, Google, Microsoft, Meta, Amazon, OpenAI, Anthropic, NVIDIAの主要ニュース。
- ユーザー影響またはプラットフォーム戦略への影響が大きいものを優先する。
- 例: AI搭載端末、OS/ブラウザ/アプリ統合、AIアシスタント、モデル公開、モデル利用制限、AIエージェント、価格変更、提供開始・終了、ハードウェア要件、チップロードマップ、AIインフラ、セキュリティ、プライバシー、規制。

Tier 2:
- 上記8社以外でも、技術的に重要なAIニュース。
- AIエージェント、オンデバイスAI、ブラウザ/アプリ操作、AIコーディング、AIセキュリティ、モデル能力、AIインフラ、チップ、メモリ、ストレージ、データセンター、電力、冷却、AI搭載端末・OSに実質的影響があるもの。

Tier 3:
- 広いAI業界ニュース。
- 競争環境、規制・アクセス、エコシステム戦略、製品方向性を変える場合だけ採用する。

同一Tier内の順位:
1. ユーザー影響とプラットフォーム重要度
2. 新しさ
3. ソース信頼性
4. ユーザーにとっての実用性
5. 技術的な面白さ

ソース方針:
- 日本語記事を優先する。ただし、英語・海外記事が一次情報、より詳細、より速い、より信頼できる、または十分な日本語記事がない場合は英語・海外記事を使う。
- 公式発表、公式ブログ、開発者向けドキュメント、一次情報を優先する。
- 有料・ペイウォール記事も、信頼性が高く重要なら扱ってよい。ただし見出しだけで採用しない。アクセス可能な本文、公式発表、記事スニペット、要約、または信頼できる非ペイウォール情報で内容を確認できる場合だけ扱う。
- 見出しだけでニュースを選ばない。見出しは釣りや誤解を招く可能性がある。
- 採用前に、記事本文または少なくとも1つの信頼できる補強ソースで、実際に何が起きたかを確認する。
- 見出ししか確認できず中身が検証できない場合は除外する。どうしても触れる場合は「未確認」と明記し、主要ニュースとして扱わない。
- Bloomberg, The Verge, 9to5Mac, MacRumors, Windows Central, Android Authority, Android Central, The Information, Reuters, CNBCなど、信頼できる媒体の噂は扱ってよい。ただし記事自体が過去24時間以内で、見出し以上の実質内容を確認できる場合に限る。
- 噂・未確認情報は、必ず「噂」または「未確認情報」と明記する。

除外条件:
- 株価だけの記事
- 決算だけの記事
- 投資家向けだけの記事
- アナリスト評価だけの記事
- 目標株価だけの記事
- M&A観測だけが中心の記事
- 内容が薄い転載記事、広告記事、SEO目的の記事

ただし、次は除外しない:
- 消費者向け製品価格の変更
- 製品提供・在庫・発売時期の変更
- サブスクリプション価格やプラン変更
- AIハードウェア費用、メモリ/ストレージ費用
- AI搭載端末の採用や普及
- それらが購入判断、ユーザー体験、プラットフォーム戦略に影響する場合

採用する各ニュースで必ず説明する観点:
- 何が起きたか
- 公開タイミング。厳密な時刻が不明なら「約」「現地時間」「過去24時間以内」などでよい
- 重要度: 高 / 中 / 低
- 信頼度: 公式 / 大手報道 / 専門メディア / 噂 / 有料記事・確認済み
- 選定理由。単に「新しい」「重要」ではなく、どの中長期トレンドにつながるかを書く
- 中長期的な意味
- 自分向けの意味。個人の製品体験、技術トレンド、購入判断、主要企業動向理解として何を意味するか
- 解釈・評価。事実と推測を分ける
- 今後の見通し。推測は見通しとして明記する
- ソースURL

選定理由で触れるべき中長期トレンド例:
- AIがOSレイヤーになる
- AIエージェントがアプリ操作やアプリ内の操作手順を置き換える
- オンデバイスAIとハードウェア要件が端末購入判断を左右する
- AIインフラがチップ、データセンター、電力、冷却へ広がる
- モデルアクセスが規制・制限される
- AIサブスクリプションや価格変更が個人・企業の採用を変える
- ビッグテックのプラットフォーム競争が変化する

出力の作り方:
1. まず `news_items` を作る。これがLINE短縮版と詳細版の唯一の正本です。
2. `news_items` はTier、ユーザー影響、プラットフォーム重要度、新しさ、信頼性、実用性、技術的興味の順で総合評価し、重要な順に並べる。
3. LINE短縮版 `line_message` は `news_items` の順序をそのまま使う。
4. 詳細版 `detailed_markdown` は Apple / Google / Microsoft / Meta/Amazon / Other AI のカテゴリ構成にする。ただし各カテゴリ内では `news_items` の相対順序、タイトル、重要度、信頼度、URLを維持する。
5. 詳細版の各ニュース見出し番号は、カテゴリ内の連番ではなく `news_items` の全体順位番号を使う。これによりLINE短縮版の番号と一致させる。
6. 各カテゴリに過去24時間以内の条件に合う主要記事がない場合は、古いニュースで埋めず「過去24時間以内に条件に合う主要ニュースはありません」と短く書く。
7. ニュースが少ない場合は水増しせず、`news_items` を3本未満にしてよい。その場合は `editor_note` とLINEの補足に「本日は条件に合う重要ニュースが少なめです」と書く。
8. `selection_basis` には、24時間の対象範囲、除外したもの、ランキングロジック、ソース方針、トップニュースを選んだ理由を3〜6件で簡潔に書く。

news_items の各項目:
- category: 必ず「Apple」「Google」「Microsoft」「Meta/Amazon」「Other AI」のいずれかにする。OpenAI、Anthropic、NVIDIA、AI半導体、AIインフラ、AI規制、その他企業は「Other AI」にまとめる。
- title: ニュース見出し。毎日読みやすい短い見出しにする。
- line_summary: LINE用の概要。2〜3文で、何が起きたかが分かる長さにする。
- summary_points: 詳細版用の3行要約。必ず3件を目安にする。
- published_timing: 「過去24時間以内」「約N時間前」「公式発表日: YYYY-MM-DD」など。24時間より古い記事を最新扱いしない。
- importance: 「高」「中」「低」のいずれか。
- reliability: 「公式」「大手報道」「専門メディア」「噂」「有料記事・確認済み」のいずれか。噂の場合はtitleまたはanalysisに必ず「噂」または「未確認情報」と書く。
- selection_reason: このニュースを選んだ理由。単に「新しい」「重要」ではなく、中長期トレンドとの接続を書く。
- long_term_significance: 中長期的な意味。製品体験、プラットフォーム戦略、技術基盤、規制、価格、アクセス制限などの観点で書く。
- user_meaning: 個人の関心、技術トレンド、製品体験、購入判断、主要企業動向の理解として何を意味するかを書く。kintone、社内業務改善、業務フロー設計、WWDC資料作成向け観点は入れない。
- analysis: 解釈・評価。事実と推測を分けて書く。
- outlook: 今後の見通し。推測は「見通し」と分かるように書く。
- source_url: ソースURL。URLがないニュースは原則採用しない。

overall_summary:
- conclusion: 今日の全体傾向を2〜4文で説明する。単なる箇条書きではなく、今日のAI・ITニュース全体が何を示しているのかを書く。
- key_points: 詳細版の「今日の結論」に使う要点を3〜5件。

must_read:
- 1〜3本。
- 必ず過去24時間以内のソースから選ぶ。
- 原則として `news_items` に含めたニュースのURLから選ぶ。
- LINE短縮版と詳細版で同じ順序にする。

deep_dive_candidates:
- 3〜5件。
- 過去24時間以内のソースに基づくテーマだけを使う。
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
必ず次の固定テンプレートで作る。カテゴリ別に整理し、各カテゴリ内ではLINE短縮版の重要ニュースと同じ相対順序にする。

# AIニュース詳細版｜YYYY年MM月DD日 7:00 JST

## Selection basis
- {{selection_basis[0]}}
- {{selection_basis[1]}}
- {{selection_basis[2]}}

## 今日の結論
- {{overall_summary.key_points[0]}}
- {{overall_summary.key_points[1]}}
- {{overall_summary.key_points[2]}}

## Apple

### 1. {{news_items[0].category}}｜{{news_items[0].title}}
- 3行要約:
  - {{news_items[0].summary_points[0]}}
  - {{news_items[0].summary_points[1]}}
  - {{news_items[0].summary_points[2]}}
- 公開タイミング: {{news_items[0].published_timing}}
- 重要度: {{news_items[0].importance}}
- 信頼度: {{news_items[0].reliability}}
- 選定理由: {{news_items[0].selection_reason}}
- 中長期的な意味: {{news_items[0].long_term_significance}}
- 自分向けの意味: {{news_items[0].user_meaning}}
- 解釈・評価: {{news_items[0].analysis}}
- 今後の見通し: {{news_items[0].outlook}}
- ソースURL: {{news_items[0].source_url}}

{{カテゴリごとに該当するnews_itemsを同じ形式で続ける。該当なしなら「過去24時間以内に条件に合う主要ニュースはありません。」と書く。}}

## Google
{{Googleカテゴリのニュース。該当なしなら短く明記。}}

## Microsoft
{{Microsoftカテゴリのニュース。該当なしなら短く明記。}}

## Meta/Amazon
{{Meta/Amazonカテゴリのニュース。該当なしなら短く明記。}}

## Other AI
{{OpenAI、Anthropic、NVIDIA、AI半導体、AIインフラ、規制、その他企業のニュース。該当なしなら短く明記。}}

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
- `news_items` の順序を、LINE短縮版・must_read候補の基準にする。
- 詳細版はカテゴリ別にするが、同じカテゴリ内では `news_items` の相対順序を守る。
- 詳細版の見出し番号は `news_items` の全体順位番号を使い、LINE短縮版の番号と一致させる。
- LINE短縮版と詳細版で、タイトル、重要度、信頼度、URLを変えない。
- 詳細版だけに重要ニュースを追加したり、LINEだけに重要ニュースを追加したりしない。
- 詳細版の文章量はLINEより長くしてよいが、ニュースの選定と順序は変えない。
- Markdownの表は使わない。
- 返答JSONには必ず date_jst, selection_basis, overall_summary, news_items, line_message, detailed_markdown, sources, must_read, deep_dive_candidates, editor_note を含める。

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
    selection_basis = _clean_string_list(data.get("selection_basis", []), limit=6)
    if not selection_basis:
        selection_basis = [
            "7:00 JSTのブリーフィング時点から過去24時間以内に公開された記事・公式発表だけを対象にしました。",
            "株価、決算、投資家向け、見出しだけで中身を確認できない記事は除外しました。",
            "ユーザー影響、プラットフォーム重要度、新しさ、信頼性、実用性、技術的興味の順に評価しました。",
        ]
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
        selection_basis=selection_basis,
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

        category = _category_bucket(raw.get("category"))
        line_summary = _clean_text(raw.get("line_summary")) or "詳細はソース記事を確認してください。"
        summary_points = _clean_string_list(raw.get("summary_points", []), limit=3)
        while len(summary_points) < 3:
            summary_points.append(line_summary)

        items.append(
            {
                "category": category,
                "title": title,
                "line_summary": line_summary,
                "summary_points": summary_points[:3],
                "published_timing": _clean_text(raw.get("published_timing")) or "公開タイミング未確認",
                "importance": _normalize_choice(raw.get("importance"), {"高", "中", "低"}, "中"),
                "reliability": _normalize_choice(
                    raw.get("reliability"),
                    {"公式", "大手報道", "専門メディア", "噂", "有料記事・確認済み"},
                    "専門メディア",
                ),
                "selection_reason": _clean_text(raw.get("selection_reason"))
                or "AIが製品体験やプラットフォーム戦略に入り込む流れと関係するため。",
                "long_term_significance": _clean_text(raw.get("long_term_significance"))
                or "中長期的には、AI機能の利用条件や端末・サービス選びに影響する可能性があります。",
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
    selection_basis: list[str],
    overall_summary: dict[str, Any],
    news_items: list[dict[str, Any]],
    must_read: list[dict[str, str]],
    deep_dive_candidates: list[str],
    editor_note: str,
) -> str:
    lines: list[str] = [
        f"# AIニュース詳細版｜{_detail_title_date(date_jst)}",
        "",
        "## Selection basis",
    ]
    lines.extend(f"- {point}" for point in selection_basis)
    lines.extend(
        [
            "",
            "## 今日の結論",
        ]
    )
    lines.extend(f"- {point}" for point in overall_summary["key_points"])
    lines.append("")

    indexed_items = list(enumerate(news_items, start=1))
    for category in ["Apple", "Google", "Microsoft", "Meta/Amazon", "Other AI"]:
        lines.extend([f"## {category}", ""])
        category_items = [
            (index, item)
            for index, item in indexed_items
            if _category_bucket(item.get("category", "")) == category
        ]
        if not category_items:
            lines.extend(["過去24時間以内に条件に合う主要ニュースはありません。", ""])
            continue

        for index, item in category_items:
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
                    f"- 選定理由: {item['selection_reason']}",
                    f"- 中長期的な意味: {item['long_term_significance']}",
                    f"- 自分向けの意味: {item['user_meaning']}",
                    f"- 解釈・評価: {item['analysis']}",
                    f"- 今後の見通し: {item['outlook']}",
                    f"- ソースURL: {item['source_url']}",
                    "",
                ]
            )

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


def _category_bucket(category: Any) -> str:
    text = _clean_text(category).lower()
    if "apple" in text or "アップル" in text:
        return "Apple"
    if "google" in text or "グーグル" in text:
        return "Google"
    if "microsoft" in text or "windows" in text or "copilot" in text:
        return "Microsoft"
    if "meta" in text or "amazon" in text or "aws" in text:
        return "Meta/Amazon"
    return "Other AI"


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

## Selection basis
- 7:00 JSTのブリーフィング時点から過去24時間以内に公開された記事・公式発表だけを対象にします。
- 株価、決算、投資家向け、見出しだけで中身を確認できない記事は除外します。
- ユーザー影響、プラットフォーム重要度、新しさ、信頼性、実用性、技術的興味の順に評価します。

## 今日の結論
- 本日はOpenAI APIまたはJSON解析でエラーが発生したため、通常のニュース収集結果を生成できませんでした。
- GitHub ActionsのログでOpenAI API、レート制限、ネットワークエラー、JSONパース失敗を確認してください。
- 本日は条件に合う重要ニュースが少なめです。

## Apple
過去24時間以内に条件に合う主要ニュースはありません。

## Google
過去24時間以内に条件に合う主要ニュースはありません。

## Microsoft
過去24時間以内に条件に合う主要ニュースはありません。

## Meta/Amazon
過去24時間以内に条件に合う主要ニュースはありません。

## Other AI
生成失敗のため掲載なし。

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

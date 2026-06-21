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

LINE短縮版 line_message:
以下の固定テンプレートに必ず従うこと。
見出し名、順番、括弧、区切り線を変えないこと。
毎回この構造で出力すること。
詳細版全文は入れないが、各ニュースの説明は短すぎないようにする。
原則として、重要ニュースは3〜5本、今日読むべき記事は1〜3本にする。
該当ニュースが少ない場合は、無理に水増ししない。

line_message は必ず以下のテンプレートで作る。

【今日の結論】
{{今日の全体傾向を2〜4文で説明する。単なる箇条書きではなく、今日のAI・ITニュース全体が何を示しているのかを書く。}}

【重要ニュース】

1. {{カテゴリ}}｜{{ニュース見出し}}
    概要：{{何が起きたかを2〜3文で説明}}
    重要度：{{高/中/低}}
    信頼度：{{公式/大手報道/専門メディア/噂}}
    意味：{{このニュースがAI・ITの流れとして何を意味するかを1〜2文で説明}}
2. {{カテゴリ}}｜{{ニュース見出し}}
    概要：{{何が起きたかを2〜3文で説明}}
    重要度：{{高/中/低}}
    信頼度：{{公式/大手報道/専門メディア/噂}}
    意味：{{このニュースがAI・ITの流れとして何を意味するかを1〜2文で説明}}
3. {{カテゴリ}}｜{{ニュース見出し}}
    概要：{{何が起きたかを2〜3文で説明}}
    重要度：{{高/中/低}}
    信頼度：{{公式/大手報道/専門メディア/噂}}
    意味：{{このニュースがAI・ITの流れとして何を意味するかを1〜2文で説明}}

{{重要ニュースが4本目・5本目まで必要な場合は、同じ形式で続ける。不要なら出さない。}}

【今日読むべき記事】

1. {{記事タイトル}}
    理由：{{なぜ読むべきかを1〜2文で説明}}
    URL：{{URL}}
2. {{記事タイトル}}
    理由：{{なぜ読むべきかを1〜2文で説明}}
    URL：{{URL}}

{{3本目が必要な場合は同じ形式で続ける。不要なら出さない。}}

【補足】
{{ニュースが少ない日、噂が多い日、公式発表が少ない日など、今日のニュースの読み方に関する補足を1〜3文で書く。不要なら「特になし」と書く。}}

詳細版: {detail_url}

LINE短縮版のルール:
- 見出しは必ず「【今日の結論】」「【重要ニュース】」「【今日読むべき記事】」「【補足】」「詳細版: URL」にする。
- 見出しの順番を変えない。
- Markdownの表は使わない。
- 箇条書きは使ってよいが、毎回テンプレートに合わせる。
- 重要ニュースごとに「概要」「重要度」「信頼度」「意味」を必ず入れる。
- 詳細版リンクは必ず {detail_url} を使う。
- line_messageには詳細版全文を入れない。
- ただし、短すぎる要約にしない。LINEで読める範囲で、文脈が分かる長さにする。
- ニュースが少ない場合は、重要ニュースを3本未満にしてもよい。その場合は【補足】で「本日は条件に合う重要ニュースが少なめです」と明記する。
- 形式が崩れそうな場合でも、必ず上記テンプレートを優先する。

詳細版 detailed_markdown:
以下の構成を日本語Markdownで作る。
詳細版は現在の構成を維持しつつ、文章量は現在より長めでよい。
各ニュースの背景、解釈、今後の見通しを厚めに書く。

# AIニュース詳細版｜YYYY年MM月DD日 7:00 JST

## 今日の結論
- 今日の全体傾向を3〜5行で要約
- 特に重要なニュースを1〜3件
- AI・IT技術全体の流れとして何が見えているかを書く

## Apple
各ニュースに、見出し、3行要約、公開タイミング、重要度、信頼度、
自分向けの意味、解釈・評価、今後の見通し、ソースURLを含める。
Apple関連で重要ニュースが少ない日は、無理に水増しせず「本日はApple関連の重要ニュースは少なめ」と書く。

## Google
同上。

## Other AI
OpenAI、Anthropic、Microsoft、Meta、xAI、Perplexity、NVIDIA、AMD、Intel、Qualcomm、Arm、AI搭載端末・OS、AI開発者ツール、AI検索、AI規制・セキュリティなどをまとめる。
各ニュースに、見出し、3行要約、公開タイミング、重要度、信頼度、自分向けの意味、解釈・評価、今後の見通し、ソースURLを含める。

## 今日読むべき記事
1〜3本。読むべき理由とURLを示す。

## 深掘り候補
3〜5件。今後追うべき理由を添える。

出力品質:
- LINE短縮版と詳細版で、重要ニュースの選定が大きく矛盾しないようにする。
- LINE短縮版は定型フォーマットを最優先する。
- 詳細版は読み物として自然にする。
- 重要度と信頼度を必ず明記する。
- URLがないニュースは原則採用しない。
- ソースが弱い場合は信頼度を下げ、噂・未確認情報として扱う。
- 古いニュースを最新ニュースのように扱わない。
- 過去24時間に限定しすぎて重要ニュースが少ない場合は、過去48時間以内まで広げてもよいが、その場合は「過去48時間以内」と分かるようにする。

実装上の注意:
- Structured Outputsのスキーマを壊さない。必ず date_jst, line_message, detailed_markdown, sources, must_read, deep_dive_candidates を含むJSONを返す。
- line_message は上記テンプレートそのものに従わせる。
- detailed_markdown は既存のMarkdown生成・HTML生成処理と互換性を保つ。
- {date_jst} と {detail_url} の埋め込みは既存の仕組みを維持する。

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

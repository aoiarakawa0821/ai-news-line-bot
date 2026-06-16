"""Entry point for daily AI news generation and LINE delivery."""

from __future__ import annotations

import logging
from datetime import datetime

from config import load_config, today_jst
from line_sender import send_line_message
from news_briefing import generate_news_briefing
from site_generator import generate_site


def setup_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s - %(message)s",
    )


def main() -> None:
    setup_logging()
    logger = logging.getLogger("main")
    logger.info("AIニュース生成処理を開始します。")

    config = load_config()
    now = today_jst()
    date_slug = now.strftime("%Y-%m-%d")
    date_label = now.strftime("%Y年%m月%d日 %H:%M")
    detail_url = build_detail_url(config.site_base_url, date_slug)

    logger.info("利用モデル: %s", config.openai_model)
    logger.info("詳細版URL: %s", detail_url or "未設定")

    briefing = generate_news_briefing(
        api_key=config.openai_api_key,
        model=config.openai_model,
        date_jst=date_label,
        detail_url=detail_url,
    )

    dated_path, latest_path, index_path = generate_site(
        detailed_markdown=briefing.detailed_markdown,
        date_slug=date_slug,
        docs_dir="docs",
    )
    logger.info("生成ファイル: %s, %s, %s", dated_path, latest_path, index_path)

    send_line_message(
        channel_access_token=config.line_channel_access_token,
        to_id=config.line_to_id,
        message=briefing.line_message,
    )

    logger.info("AIニュース生成処理が完了しました。")


def build_detail_url(site_base_url: str, date_slug: str) -> str:
    if not site_base_url:
        return ""
    return f"{site_base_url.rstrip('/')}/{date_slug}.html"


if __name__ == "__main__":
    main()


"""Entry point for daily AI news generation and LINE delivery."""

from __future__ import annotations

import logging

from approved_users import resolve_delivery_targets
from config import load_config, today_jst
from daily_run_guard import already_sent_today, is_scheduled_run, write_sent_marker
from line_sender import send_line_message_to_many
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
    scheduled_run = is_scheduled_run()

    if scheduled_run and already_sent_today(date_slug):
        logger.info(
            "本日分は送信済みマーカーがあるため、schedule実行をスキップします。date=%s",
            date_slug,
        )
        logger.info("AIニュース生成処理が完了しました。")
        return

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

    delivery_targets = resolve_delivery_targets(config)
    logger.info(
        "LINE送信先を解決しました。mode=%s count=%s",
        delivery_targets.mode,
        len(delivery_targets.to_ids),
    )

    if not delivery_targets.to_ids:
        logger.warning("送信先が0件のため、LINE送信をスキップします。mode=%s", delivery_targets.mode)
        logger.info("AIニュース生成処理が完了しました。")
        return

    line_message = briefing.line_message
    if delivery_targets.warning_message:
        line_message = f"{delivery_targets.warning_message}\n\n{line_message}"

    summary = send_line_message_to_many(
        channel_access_token=config.line_channel_access_token,
        to_ids=delivery_targets.to_ids,
        message=line_message,
    )
    logger.info("LINE送信結果: success=%s failure=%s", summary.success_count, summary.failure_count)

    marker_reason = _sent_marker_skip_reason(
        scheduled_run=scheduled_run,
        briefing_is_fallback=briefing.is_fallback,
        delivery_mode=delivery_targets.mode,
        success_count=summary.success_count,
        failure_count=summary.failure_count,
    )

    if not marker_reason:
        marker = write_sent_marker(
            date_slug=date_slug,
            delivery_mode=delivery_targets.mode,
            target_count=len(delivery_targets.to_ids),
            success_count=summary.success_count,
            failure_count=summary.failure_count,
        )
        logger.info("本日分の送信済みマーカーを作成しました。file=%s", marker)
    elif scheduled_run:
        logger.warning("送信済みマーカーは作成しません。reason=%s", marker_reason)

    logger.info("AIニュース生成処理が完了しました。")


def build_detail_url(site_base_url: str, date_slug: str) -> str:
    if not site_base_url:
        return ""
    return f"{site_base_url.rstrip('/')}/{date_slug}.html"


def _sent_marker_skip_reason(
    *,
    scheduled_run: bool,
    briefing_is_fallback: bool,
    delivery_mode: str,
    success_count: int,
    failure_count: int,
) -> str:
    if not scheduled_run:
        return "not_scheduled_run"
    if briefing_is_fallback:
        return "news_generation_fallback"
    if delivery_mode == "APPROVED_USERS_ENDPOINT_FALLBACK_ADMIN":
        return "approved_users_endpoint_fallback_admin_only"
    if success_count <= 0:
        return "no_successful_line_delivery"
    if failure_count > 0:
        return "partial_line_delivery_failure"
    return ""


if __name__ == "__main__":
    main()

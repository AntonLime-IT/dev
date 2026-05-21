"""
Точка входа: запуск Telegram-бота с интеграцией Claude.
"""
import asyncio
import logging
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
)

from config import TELEGRAM_BOT_TOKEN
import handlers as h

logging.basicConfig(
    format="%(asctime)s | %(levelname)-8s | %(name)s: %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


def build_app() -> Application:
    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    # ── Команды ──────────────────────────────────────────────────────────
    app.add_handler(CommandHandler("start", h.cmd_start))
    app.add_handler(CommandHandler("help",  h.cmd_help))
    app.add_handler(CommandHandler("post",    h.cmd_post))
    app.add_handler(CommandHandler("analyze", h.cmd_analyze))
    app.add_handler(CommandHandler("improve", h.cmd_improve))
    app.add_handler(CommandHandler("reply",   h.cmd_reply))
    app.add_handler(CommandHandler("publish", h.cmd_publish))
    app.add_handler(CommandHandler("summary", h.cmd_summary))
    app.add_handler(CommandHandler("ask",     h.cmd_ask))
    app.add_handler(CommandHandler("posts",   h.cmd_posts))

    # ── Посты из канала (автосохранение) ─────────────────────────────────
    app.add_handler(MessageHandler(filters.ChatType.CHANNEL, h.handle_channel_post))

    # ── Inline-кнопки ────────────────────────────────────────────────────
    app.add_handler(CallbackQueryHandler(h.handle_callback))

    # ── Текстовые сообщения / пересылка ──────────────────────────────────
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, h.handle_text))

    return app


def main():
    logger.info("Запуск бота…")
    # Python 3.10+ больше не создаёт event loop автоматически — делаем сами
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    app = build_app()
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()

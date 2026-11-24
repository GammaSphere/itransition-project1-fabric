"""Telegram bot: /quality runs the data-quality checks and replies with a report."""
import asyncio
import io
import logging
import os

from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

from integrations.common.reader import TABLES
from integrations.dq_bot.report import format_summary, render_html
from integrations.dq_bot.suites import run_checks

log = logging.getLogger("dq_bot")


def allowed_chats():
    return {int(c) for c in os.environ.get("TELEGRAM_ALLOWED_CHAT_IDS", "").split(",") if c.strip()}


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.effective_message.reply_text(
        f"Your chat ID is {update.effective_chat.id}.\n"
        "Send /quality to check every gold table, or /quality <table> for one."
    )


async def quality(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.effective_message
    if update.effective_chat.id not in allowed_chats():
        await message.reply_text("Not authorised")
        return
    unknown = [t for t in context.args or [] if t not in TABLES]
    if unknown:
        await message.reply_text(f"Unknown table: {', '.join(unknown)}.\nTables: {', '.join(sorted(TABLES))}")
        return
    await message.reply_text("Running data-quality checks…")
    try:
        results = await asyncio.to_thread(run_checks, context.args or None)
    except Exception:  # never echo driver errors to the chat: they can contain connection details
        log.exception("quality run failed")
        await message.reply_text("The checks could not run. See the bot log for details.")
        return
    await message.reply_text(format_summary(results))
    await message.reply_document(io.BytesIO(render_html(results)), filename="quality_report.html")


def setup_logging():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
    # httpx logs every request URL at INFO, and Telegram URLs contain the bot token.
    logging.getLogger("httpx").setLevel(logging.WARNING)


def main():
    setup_logging()
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not token:
        log.warning("TELEGRAM_BOT_TOKEN is not set; the bot is not started")
        return
    app = Application.builder().token(token).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("quality", quality))
    app.run_polling()


if __name__ == "__main__":
    main()

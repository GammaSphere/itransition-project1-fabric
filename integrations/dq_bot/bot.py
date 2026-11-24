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
    await update.message.reply_text(
        f"Your chat ID is {update.effective_chat.id}.\n"
        "Send /quality to check every gold table, or /quality <table> for one.\n"
        f"Tables: {', '.join(sorted(TABLES))}"
    )


async def quality(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.id not in allowed_chats():
        await update.message.reply_text("Not authorised")
        return
    await update.message.reply_text("Running data-quality checks…")
    try:
        results = await asyncio.to_thread(run_checks, context.args or None)
    except ValueError as e:  # unknown table name
        await update.message.reply_text(str(e))
        return
    except Exception:
        log.exception("quality run failed")
        await update.message.reply_text("The checks could not run. See the bot log for details.")
        return
    await update.message.reply_text(format_summary(results))
    await update.message.reply_document(io.BytesIO(render_html(results)), filename="quality_report.html")


def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
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

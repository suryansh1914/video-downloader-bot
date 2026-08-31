"""
Telegram Video Downloader Bot — entry point.

Simple bot: send a link → get the video. No processing, no ffmpeg needed.
Supports YouTube, Instagram, TikTok, Facebook, and 1000+ other sites.
"""

from __future__ import annotations

import asyncio
import logging
import sys
from pathlib import Path

from telegram import Update
from telegram.constants import ChatAction, ParseMode
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

import config
from downloader import DownloadError, download_video
from models import Job, JobStatus
from queue_manager import QueueManager, RateLimitExceeded
from utils import cleanup_job_dir, detect_url, file_size_mb, platform_label

# ─── Logging ────────────────────────────────────────────────────────────────

logging.basicConfig(
    level=getattr(logging, config.LOG_LEVEL, logging.INFO),
    format="%(asctime)s | %(name)-18s | %(levelname)-7s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

# ─── Globals ────────────────────────────────────────────────────────────────

queue_mgr = QueueManager()

# ─── Messages ───────────────────────────────────────────────────────────────

WELCOME_TEXT = """👋 *Video Downloader Bot*

Send me any video link and I'll download it for you\\!

🔴 YouTube \\(videos, shorts, live\\)
📸 Instagram \\(reels, posts, stories\\)
🎵 TikTok
🔵 Facebook
🌐 \\+1000 other sites

*How to use:*
Just send a link — that's it\\!

📊 /status — check current download
❌ /cancel — cancel download
ℹ️ /help — show this message

⚡ _Powered by yt\\-dlp_"""

HELP_TEXT = """ℹ️ *How to use this bot:*

1️⃣ Copy a video link from YouTube, Instagram, TikTok, or Facebook
2️⃣ Paste it here
3️⃣ Wait for download
4️⃣ Get your video\\!

*Limits:*
• Max duration: {max_dur} minutes
• Max file size: {max_size} MB
• {rate_limit} downloads per hour

*Supported platforms:*
YouTube, Instagram, TikTok, Facebook, Twitter/X, Reddit, Vimeo, Dailymotion, and 1000\\+ more\\!"""


# ─── /start ─────────────────────────────────────────────────────────────────

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(WELCOME_TEXT, parse_mode=ParseMode.MARKDOWN_V2)


# ─── /help ──────────────────────────────────────────────────────────────────

async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = HELP_TEXT.format(
        max_dur=config.MAX_DURATION_SECONDS // 60,
        max_size=config.MAX_FILE_SIZE_MB,
        rate_limit=config.RATE_LIMIT_PER_HOUR,
    )
    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN_V2)


# ─── /status ────────────────────────────────────────────────────────────────

async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    job = queue_mgr.get_active_job(user_id)
    if not job:
        await update.message.reply_text("ℹ️ No active download right now.")
        return

    icons = {
        JobStatus.QUEUED: "🕐 Waiting...",
        JobStatus.DOWNLOADING: "⬇️ Downloading...",
        JobStatus.UPLOADING: "⬆️ Sending to you...",
    }
    label = icons.get(job.status, job.status.value.title())
    await update.message.reply_text(f"📊 *Status:* {label}", parse_mode=ParseMode.MARKDOWN)


# ─── /cancel ────────────────────────────────────────────────────────────────

async def cmd_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    job = queue_mgr.cancel_job(user_id)
    if job:
        cleanup_job_dir(job.job_dir)
        await update.message.reply_text("✅ Download cancelled.")
    else:
        await update.message.reply_text("ℹ️ No active download to cancel.")


# ─── Link handler (main flow) ──────────────────────────────────────────────

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Detect a URL and download the video."""
    text = update.message.text or ""
    url = detect_url(text)

    if not url:
        await update.message.reply_text(
            "🔗 Send me a valid video link (YouTube, Instagram, TikTok, Facebook)."
        )
        return

    user_id = update.effective_user.id
    chat_id = update.effective_chat.id

    # Check active job
    if queue_mgr.has_active_job(user_id):
        await update.message.reply_text(
            "⏳ You already have a download running. Use /cancel to stop it."
        )
        return

    # Rate limit
    try:
        queue_mgr.check_rate_limit(user_id)
    except RateLimitExceeded as exc:
        await update.message.reply_text(str(exc))
        return

    # Create job
    job = Job(user_id=user_id, chat_id=chat_id, url=url)
    job.job_dir = config.TEMP_DIR / job.job_id
    job.job_dir.mkdir(parents=True, exist_ok=True)

    queue_mgr.register_job(job)

    status_msg = await update.message.reply_text("⬇️ Downloading your video...")
    job.message_id = status_msg.message_id

    # Run in background
    asyncio.create_task(_download_pipeline(job, context))


async def _download_pipeline(job: Job, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Download → send pipeline for one job."""
    bot = context.bot

    async def _edit(text: str) -> None:
        try:
            await bot.edit_message_text(
                chat_id=job.chat_id, message_id=job.message_id, text=text,
                parse_mode=ParseMode.MARKDOWN,
            )
        except Exception:
            pass

    try:
        await queue_mgr.acquire()

        if job.status == JobStatus.CANCELLED:
            return

        # ── Download ────────────────────────────────────────────────────
        job.status = JobStatus.DOWNLOADING
        await bot.send_chat_action(chat_id=job.chat_id, action=ChatAction.TYPING)

        try:
            file_path, metadata = await asyncio.wait_for(
                download_video(job.url, job.job_dir),
                timeout=config.JOB_TIMEOUT_SECONDS,
            )
        except asyncio.TimeoutError:
            raise DownloadError("⏱ Download timed out. Try a shorter video.")

        job.file_path = file_path
        job.metadata = metadata

        if job.status == JobStatus.CANCELLED:
            return

        # ── Check file size for Telegram ────────────────────────────────
        size = file_size_mb(file_path)
        if size > config.TELEGRAM_UPLOAD_LIMIT_MB:
            raise DownloadError(
                f"📦 Video is {size:.0f} MB — exceeds Telegram's "
                f"{config.TELEGRAM_UPLOAD_LIMIT_MB} MB upload limit. "
                f"Try a shorter video or lower quality source."
            )

        # ── Upload to user ──────────────────────────────────────────────
        job.status = JobStatus.UPLOADING
        plabel = platform_label(metadata.source_platform)
        await _edit(f"⬆️ Sending *{metadata.title[:40]}*... ({size:.1f} MB)")
        await bot.send_chat_action(chat_id=job.chat_id, action=ChatAction.UPLOAD_VIDEO)

        duration_str = ""
        if metadata.duration:
            mins = int(metadata.duration // 60)
            secs = int(metadata.duration % 60)
            duration_str = f" | ⏱ {mins}:{secs:02d}"

        caption = (
            f"{plabel}\n"
            f"📹 {metadata.title}\n"
            f"📦 {size:.1f} MB{duration_str}"
        )

        with open(file_path, "rb") as f:
            await bot.send_video(
                chat_id=job.chat_id,
                video=f,
                caption=caption,
                supports_streaming=True,
                read_timeout=120,
                write_timeout=120,
            )

        # ── Done ────────────────────────────────────────────────────────
        job.status = JobStatus.DONE
        await _edit("✅ Video sent!")
        logger.info("Job %s done — %s (%.1f MB)", job.job_id, metadata.title, size)

    except DownloadError as exc:
        job.status = JobStatus.FAILED
        job.error = str(exc)
        await _edit(str(exc))
        logger.warning("Job %s failed: %s", job.job_id, exc)

    except Exception as exc:
        job.status = JobStatus.FAILED
        job.error = str(exc)
        await _edit(f"❌ Something went wrong:\n{exc}")
        logger.exception("Unexpected error in job %s", job.job_id)

    finally:
        queue_mgr.release()
        await queue_mgr.log_job(job)
        queue_mgr.unregister_job(job.user_id)
        cleanup_job_dir(job.job_dir)


# ─── Dummy Web Server for Render ────────────────────────────────────────────

from aiohttp import web

async def _health_check(request):
    """Simple health check endpoint for Render."""
    return web.Response(text="Bot is running!")

async def start_dummy_server():
    """Starts a dummy aiohttp server on the PORT env variable."""
    app = web.Application()
    app.add_routes([web.get("/", _health_check)])
    runner = web.AppRunner(app)
    await runner.setup()
    
    port = config.PORT
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    logger.info("🌐 Dummy web server running on port %d (for Render)", port)

# ─── Main ───────────────────────────────────────────────────────────────────

def main() -> None:
    if not config.BOT_TOKEN:
        logger.error("BOT_TOKEN not set! Copy .env.example → .env and add your token.")
        sys.exit(1)

    app = Application.builder().token(config.BOT_TOKEN).build()

    # Commands
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(CommandHandler("status", cmd_status))
    app.add_handler(CommandHandler("cancel", cmd_cancel))

    # Plain messages → link detection
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    # Lifecycle
    async def on_startup(application: Application) -> None:
        await queue_mgr.start()
        await start_dummy_server()
        logger.info("🤖 Bot started!")

    async def on_shutdown(application: Application) -> None:
        await queue_mgr.stop()
        logger.info("Bot shut down.")

    app.post_init = on_startup
    app.post_shutdown = on_shutdown

    logger.info("Starting Video Downloader Bot...")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()

"""
Configuration — loads .env and defines all bot constants.
Simple video downloader version (no ffmpeg processing).
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env from project root
load_dotenv(Path(__file__).parent / ".env")

# ─── Telegram ───────────────────────────────────────────────────────────────
BOT_TOKEN: str = os.getenv("BOT_TOKEN", "")

# ─── Limits ─────────────────────────────────────────────────────────────────
MAX_DURATION_SECONDS: int = int(os.getenv("MAX_DURATION_SECONDS", "600"))       # 10 min
MAX_FILE_SIZE_MB: int = int(os.getenv("MAX_FILE_SIZE_MB", "200"))               # 200 MB download cap
TELEGRAM_UPLOAD_LIMIT_MB: int = int(os.getenv("TELEGRAM_UPLOAD_LIMIT_MB", "50"))  # Bot API default
MAX_CONCURRENT_JOBS: int = int(os.getenv("MAX_CONCURRENT_JOBS", "3"))
RATE_LIMIT_PER_HOUR: int = int(os.getenv("RATE_LIMIT_PER_HOUR", "10"))
JOB_TIMEOUT_SECONDS: int = int(os.getenv("JOB_TIMEOUT_SECONDS", "300"))        # 5 min

# ─── Paths ──────────────────────────────────────────────────────────────────
TEMP_DIR: Path = Path(os.getenv("TEMP_DIR", Path(__file__).parent / "tmp" / "jobs"))

# ─── Database ───────────────────────────────────────────────────────────────
DB_PATH: Path = Path(os.getenv("DB_PATH", Path(__file__).parent / "data" / "bot.db"))

# ─── Logging ────────────────────────────────────────────────────────────────
LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")

# ─── Render deployment ─────────────────────────────────────────────────────
PORT: int = int(os.getenv("PORT", "10000"))  # Render assigns PORT env var

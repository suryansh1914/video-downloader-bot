"""
Utility helpers — URL detection, cleanup, file size check.
"""

from __future__ import annotations

import logging
import re
import shutil
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# ─── URL detection ──────────────────────────────────────────────────────────

_URL_RE = re.compile(
    r"https?://(?:www\.|m\.|vm\.|vt\.|fb\.|web\.)?"
    r"(?:"
    r"youtube\.com/(?:watch|shorts|embed|v|live)"
    r"|youtu\.be/"
    r"|instagram\.com/(?:reel|p|tv|stories)/"
    r"|tiktok\.com/"
    r"|facebook\.com/"
    r"|fb\.watch/"
    r"|[\w.-]+\.[\w]{2,}/\S*"
    r")"
    r"\S*",
    re.IGNORECASE,
)


def detect_url(text: str) -> Optional[str]:
    """Return the first HTTP(S) URL found in *text*, or ``None``."""
    m = _URL_RE.search(text)
    return m.group(0).rstrip(".,;:!?)>\"'") if m else None


def detect_platform(url: str) -> str:
    """Guess source platform from the URL domain."""
    low = url.lower()
    if "youtube.com" in low or "youtu.be" in low:
        return "youtube"
    if "instagram.com" in low:
        return "instagram"
    if "tiktok.com" in low:
        return "tiktok"
    if "facebook.com" in low or "fb.watch" in low or "fb.com" in low:
        return "facebook"
    return "other"


_PLATFORM_EMOJI = {
    "youtube": "🔴 YouTube",
    "instagram": "📸 Instagram",
    "tiktok": "🎵 TikTok",
    "facebook": "🔵 Facebook",
    "other": "🌐 Video",
}


def platform_label(platform: str) -> str:
    return _PLATFORM_EMOJI.get(platform, "🌐 Video")


# ─── File helpers ───────────────────────────────────────────────────────────

def file_size_mb(path: Path) -> float:
    """Return file size in megabytes."""
    return path.stat().st_size / (1024 * 1024) if path.exists() else 0.0


def cleanup_job_dir(job_dir: Optional[Path]) -> None:
    """Delete the job's temporary directory tree."""
    try:
        if job_dir and job_dir.exists():
            shutil.rmtree(job_dir, ignore_errors=True)
            logger.info("Cleaned up %s", job_dir)
    except Exception as exc:
        logger.error("Cleanup failed for %s: %s", job_dir, exc)

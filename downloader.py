"""
Download module — wraps yt-dlp to fetch videos from YouTube, Instagram,
TikTok, Facebook, and any other supported site.

Downloads in the best available quality as a single MP4 file.
"""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path

import yt_dlp

from config import MAX_DURATION_SECONDS, MAX_FILE_SIZE_MB
from models import VideoMetadata
from utils import detect_platform

logger = logging.getLogger(__name__)

# Errors that indicate private / login-required content
_PRIVATE_ERRORS = (
    "login",
    "private",
    "sign in",
    "authentication",
    "age-restricted",
    "age gate",
    "not available",
    "requires payment",
    "video is unavailable",
)


class DownloadError(Exception):
    """Raised when a download fails with a user-friendly message."""


def _is_private_error(msg: str) -> bool:
    low = msg.lower()
    return any(kw in low for kw in _PRIVATE_ERRORS)


def _build_ydl_opts(job_dir: Path) -> dict:
    """Build yt-dlp options dict — best quality single MP4."""
    return {
        # Prefer a single file that doesn't need merging (no ffmpeg needed).
        # If only separate video+audio available, yt-dlp will merge with ffmpeg.
        "format": (
            "best[ext=mp4][filesize<50M]/"
            "bestvideo[ext=mp4]+bestaudio[ext=m4a]/"
            "best[ext=mp4]/"
            "best"
        ),
        "outtmpl": str(job_dir / "%(title).70s.%(ext)s"),
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
        "socket_timeout": 30,
        "retries": 3,
        "fragment_retries": 3,
        "merge_output_format": "mp4",
        # Extract thumbnail URL but don't download it
        "writethumbnail": False,
    }


async def _extract_info(url: str, ydl_opts: dict) -> dict:
    """Run yt-dlp info extraction in a thread."""
    def _extract():
        with yt_dlp.YoutubeDL({**ydl_opts, "skip_download": True}) as ydl:
            return ydl.extract_info(url, download=False)
    return await asyncio.to_thread(_extract)


async def _download(url: str, ydl_opts: dict) -> str:
    """Run the actual download in a thread. Returns the downloaded filepath."""
    downloaded_path = None

    def _progress_hook(d: dict):
        nonlocal downloaded_path
        if d.get("status") == "finished":
            downloaded_path = d.get("filename")

    opts = {**ydl_opts, "progress_hooks": [_progress_hook]}

    def _run():
        with yt_dlp.YoutubeDL(opts) as ydl:
            ydl.download([url])

    await asyncio.to_thread(_run)

    if not downloaded_path:
        # Fallback: find the first video file in job dir
        job_dir = Path(ydl_opts["outtmpl"]).parent
        for ext in ("*.mp4", "*.mkv", "*.webm", "*.mov"):
            files = list(job_dir.glob(ext))
            if files:
                downloaded_path = str(files[0])
                break

    if not downloaded_path or not Path(downloaded_path).exists():
        raise DownloadError("❌ Download completed but output file not found.")

    return downloaded_path


async def download_video(
    url: str,
    job_dir: Path,
    max_duration: int = MAX_DURATION_SECONDS,
    max_file_size_mb: int = MAX_FILE_SIZE_MB,
) -> tuple[Path, VideoMetadata]:
    """
    Download a video from *url* into *job_dir*.
    Returns ``(file_path, metadata)``.
    Raises :class:`DownloadError` with a user-friendly message on failure.
    """
    job_dir.mkdir(parents=True, exist_ok=True)
    ydl_opts = _build_ydl_opts(job_dir)
    platform = detect_platform(url)

    # ── Step 1: extract info to check duration ──────────────────────────
    try:
        info = await _extract_info(url, ydl_opts)
    except yt_dlp.utils.DownloadError as exc:
        msg = str(exc)
        if _is_private_error(msg):
            raise DownloadError(
                "🔒 This content is private or requires login and can't be downloaded."
            ) from exc
        raise DownloadError(f"❌ Couldn't fetch video info:\n{msg}") from exc
    except Exception as exc:
        raise DownloadError(f"❌ Unexpected error:\n{exc}") from exc

    if not info:
        raise DownloadError("❌ No video info found — the link may be invalid.")

    duration = info.get("duration") or 0
    title = info.get("title", "video")
    thumbnail = info.get("thumbnail", "")

    if duration > max_duration:
        mins = int(duration // 60)
        max_mins = int(max_duration // 60)
        raise DownloadError(
            f"⏱ Video is too long ({mins} min). Maximum allowed is {max_mins} min."
        )

    # Estimated file size check
    file_size_approx = info.get("filesize") or info.get("filesize_approx") or 0
    if file_size_approx and (file_size_approx / (1024 * 1024)) > max_file_size_mb:
        raise DownloadError(
            f"📦 Video is too large (~{file_size_approx / (1024*1024):.0f} MB). "
            f"Max allowed: {max_file_size_mb} MB."
        )

    # ── Step 2: download ────────────────────────────────────────────────
    try:
        downloaded_path = await _download(url, ydl_opts)
    except yt_dlp.utils.DownloadError as exc:
        msg = str(exc)
        if _is_private_error(msg):
            raise DownloadError(
                "🔒 This content is private or requires login."
            ) from exc
        raise DownloadError(f"❌ Download failed:\n{msg}") from exc
    except DownloadError:
        raise
    except Exception as exc:
        raise DownloadError(f"❌ Unexpected download error:\n{exc}") from exc

    path = Path(downloaded_path)

    # Post-download size check
    actual_size_mb = path.stat().st_size / (1024 * 1024)
    if actual_size_mb > max_file_size_mb:
        raise DownloadError(
            f"📦 Downloaded file is {actual_size_mb:.0f} MB, exceeding the "
            f"{max_file_size_mb} MB limit."
        )

    meta = VideoMetadata(
        title=title,
        duration=duration,
        source_platform=platform,
        width=info.get("width", 0) or 0,
        height=info.get("height", 0) or 0,
        file_size_mb=actual_size_mb,
        thumbnail=thumbnail,
    )

    logger.info(
        "Downloaded: %s [%s] — %.1f MB, %.0fs",
        title, platform, actual_size_mb, duration,
    )
    return path, meta

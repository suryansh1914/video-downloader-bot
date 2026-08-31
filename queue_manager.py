"""
Async job queue with concurrency control, rate limiting, and job logging.
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections import defaultdict
from typing import Optional

import aiosqlite

import config
from models import Job, JobStatus

logger = logging.getLogger(__name__)


class RateLimitExceeded(Exception):
    """Raised when a user has exceeded their per-hour job limit."""


class QueueManager:
    """
    Manages the video download job queue.
    Caps concurrent downloads, rate-limits per user, logs to SQLite.
    """

    def __init__(self) -> None:
        self._semaphore = asyncio.Semaphore(config.MAX_CONCURRENT_JOBS)
        self._active_jobs: dict[int, Job] = {}
        self._user_timestamps: dict[int, list[float]] = defaultdict(list)
        self._db: Optional[aiosqlite.Connection] = None

    async def start(self) -> None:
        config.DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        self._db = await aiosqlite.connect(str(config.DB_PATH))
        await self._db.execute("""
            CREATE TABLE IF NOT EXISTS job_log (
                job_id      TEXT PRIMARY KEY,
                user_id     INTEGER,
                url         TEXT,
                platform    TEXT,
                status      TEXT,
                duration_s  REAL,
                file_size_mb REAL,
                error       TEXT,
                created_at  TEXT,
                finished_at TEXT
            )
        """)
        await self._db.commit()
        logger.info("QueueManager started — DB at %s", config.DB_PATH)

    async def stop(self) -> None:
        if self._db:
            await self._db.close()
            self._db = None

    # ── Rate limiting ───────────────────────────────────────────────────

    def _prune_timestamps(self, user_id: int) -> None:
        cutoff = time.time() - 3600
        self._user_timestamps[user_id] = [
            t for t in self._user_timestamps[user_id] if t > cutoff
        ]

    def check_rate_limit(self, user_id: int) -> None:
        self._prune_timestamps(user_id)
        if len(self._user_timestamps[user_id]) >= config.RATE_LIMIT_PER_HOUR:
            raise RateLimitExceeded(
                f"⏳ Limit reached ({config.RATE_LIMIT_PER_HOUR}/hour). Try again later."
            )

    def _record_usage(self, user_id: int) -> None:
        self._user_timestamps[user_id].append(time.time())

    # ── Job tracking ────────────────────────────────────────────────────

    def has_active_job(self, user_id: int) -> bool:
        return user_id in self._active_jobs

    def get_active_job(self, user_id: int) -> Optional[Job]:
        return self._active_jobs.get(user_id)

    def register_job(self, job: Job) -> None:
        self.check_rate_limit(job.user_id)
        self._record_usage(job.user_id)
        self._active_jobs[job.user_id] = job

    def unregister_job(self, user_id: int) -> None:
        self._active_jobs.pop(user_id, None)

    def cancel_job(self, user_id: int) -> Optional[Job]:
        job = self._active_jobs.pop(user_id, None)
        if job:
            job.status = JobStatus.CANCELLED
        return job

    # ── Concurrency gate ────────────────────────────────────────────────

    async def acquire(self) -> None:
        await self._semaphore.acquire()

    def release(self) -> None:
        self._semaphore.release()

    # ── Job logging ─────────────────────────────────────────────────────

    async def log_job(self, job: Job) -> None:
        if not self._db:
            return
        try:
            await self._db.execute(
                """
                INSERT INTO job_log (job_id, user_id, url, platform, status,
                                     duration_s, file_size_mb, error, created_at, finished_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
                ON CONFLICT(job_id) DO UPDATE SET
                    status=excluded.status, error=excluded.error,
                    finished_at=excluded.finished_at
                """,
                (
                    job.job_id, job.user_id, job.url,
                    job.metadata.source_platform if job.metadata else "unknown",
                    job.status.value,
                    job.metadata.duration if job.metadata else 0,
                    job.metadata.file_size_mb if job.metadata else 0,
                    job.error,
                    job.created_at.isoformat(),
                ),
            )
            await self._db.commit()
        except Exception as exc:
            logger.error("Failed to log job %s: %s", job.job_id, exc)

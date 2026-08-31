"""
Data models — simplified for video downloader (no processing settings).
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Optional


class JobStatus(Enum):
    QUEUED = "queued"
    DOWNLOADING = "downloading"
    UPLOADING = "uploading"
    DONE = "done"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class VideoMetadata:
    """Metadata extracted from a downloaded video."""
    title: str = ""
    duration: float = 0.0
    source_platform: str = "unknown"
    width: int = 0
    height: int = 0
    file_size_mb: float = 0.0
    thumbnail: str = ""

    @property
    def aspect_ratio(self) -> float:
        if self.height == 0:
            return 1.0
        return self.width / self.height


@dataclass
class Job:
    """Represents a single video download job."""
    job_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    user_id: int = 0
    chat_id: int = 0
    message_id: int = 0
    url: str = ""
    status: JobStatus = JobStatus.QUEUED
    created_at: datetime = field(default_factory=datetime.utcnow)
    job_dir: Optional[Path] = None
    file_path: Optional[Path] = None
    metadata: Optional[VideoMetadata] = None
    error: Optional[str] = None

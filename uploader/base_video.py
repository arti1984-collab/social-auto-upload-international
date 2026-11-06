from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path


class BaseVideoUploader:
    SUPPORTED_VIDEO_EXTENSIONS = {
        ".mp4",
        ".mov",
        ".avi",
        ".mkv",
        ".m4v",
        ".webm",
        ".flv",
        ".wmv",
    }
    SUPPORTED_IMAGE_EXTENSIONS = {
        ".jpg",
        ".jpeg",
        ".png",
        ".webp",
        ".bmp",
    }
    MIN_SCHEDULE_LEAD_TIME = timedelta(hours=2)

    @classmethod
    def validate_video_file(cls, file_path: str | Path) -> Path:
        path = Path(file_path).expanduser().resolve()
        if not path.exists():
            raise FileNotFoundError(f"Video file not found: {path}")
        if not path.is_file():
            raise ValueError(f"Video path is not a file: {path}")
        if path.suffix.lower() not in cls.SUPPORTED_VIDEO_EXTENSIONS:
            raise ValueError(
                f"Unsupported video format: {path.suffix}, supported:: {', '.join(sorted(cls.SUPPORTED_VIDEO_EXTENSIONS))}"
            )

        return path

    @classmethod
    def validate_image_file(cls, file_path: str | Path) -> Path:
        path = Path(file_path).expanduser().resolve()
        if not path.exists():
            raise FileNotFoundError(f"Image file not found: {path}")
        if not path.is_file():
            raise ValueError(f"Image path is not a file: {path}")
        if path.suffix.lower() not in cls.SUPPORTED_IMAGE_EXTENSIONS:
            raise ValueError(
                f"Unsupported image format: {path.suffix}, supported:: {', '.join(sorted(cls.SUPPORTED_IMAGE_EXTENSIONS))}"
            )
        return path

    @classmethod
    def validate_publish_date(cls, publish_date: datetime | int | None) -> datetime | int:
        if publish_date in (None, 0):
            return 0

        if not isinstance(publish_date, datetime):
            raise TypeError("publish_date must be a datetime or 0")

        now = datetime.now(tz=publish_date.tzinfo) if publish_date.tzinfo else datetime.now()
        if publish_date <= now:
            raise ValueError("Scheduled publish time must be in the future")

        min_publish_time = now + cls.MIN_SCHEDULE_LEAD_TIME
        if publish_date <= min_publish_time:
            raise ValueError("Scheduled publish time must be more than 2 hours in the future")

        return publish_date

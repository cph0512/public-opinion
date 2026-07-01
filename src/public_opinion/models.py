"""共用資料模型。"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Any


@dataclass
class Post:
    """一則來自任一平台的貼文 / 留言。"""

    platform: str                       # "reddit" / "dcard" / "threads" / "facebook"
    post_id: str                        # 平台內的原始 ID
    title: str
    content: str
    url: str
    author: str = ""
    created_at: datetime | None = None  # UTC aware datetime
    score: int = 0                      # 讚 / upvote 數
    num_comments: int = 0
    matched_keywords: list[str] = field(default_factory=list)
    extra: dict[str, Any] = field(default_factory=dict)

    @property
    def dedup_key(self) -> str:
        """跨執行去重用的穩定鍵。"""
        raw = f"{self.platform}:{self.post_id}"
        return hashlib.sha1(raw.encode("utf-8")).hexdigest()

    @property
    def preview(self) -> str:
        text = (self.title or self.content or "").strip().replace("\n", " ")
        return text[:200]

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["created_at"] = self.created_at.isoformat() if self.created_at else None
        d["dedup_key"] = self.dedup_key
        return d


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def from_unix(ts: float | int | None) -> datetime | None:
    if ts is None:
        return None
    try:
        return datetime.fromtimestamp(float(ts), tz=timezone.utc)
    except (ValueError, OSError, OverflowError):
        return None


def parse_iso(value: str | None) -> datetime | None:
    """寬鬆解析 ISO8601;失敗回傳 None。"""
    if not value:
        return None
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(text)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)

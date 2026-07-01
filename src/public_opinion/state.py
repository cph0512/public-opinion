"""去重狀態:記住已經回報過的貼文,讓每天只報新內容。"""

from __future__ import annotations

import json
from pathlib import Path

from .models import Post, utc_now


class SeenStore:
    """把看過的 dedup_key 存成 JSON。"""

    def __init__(self, path: str = "state/seen.json", max_keys: int = 50_000):
        self.path = Path(path)
        self.max_keys = max_keys
        self._seen: dict[str, str] = {}  # key -> 第一次看到的時間(ISO)
        self._load()

    def _load(self) -> None:
        if self.path.exists():
            try:
                self._seen = json.loads(self.path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                self._seen = {}

    def is_new(self, post: Post) -> bool:
        return post.dedup_key not in self._seen

    def filter_new(self, posts: list[Post]) -> list[Post]:
        """回傳尚未看過的貼文(同一批內也會去重)。"""
        fresh: list[Post] = []
        batch_keys: set[str] = set()
        for post in posts:
            key = post.dedup_key
            if key in self._seen or key in batch_keys:
                continue
            batch_keys.add(key)
            fresh.append(post)
        return fresh

    def mark(self, posts: list[Post]) -> None:
        now = utc_now().isoformat()
        for post in posts:
            self._seen.setdefault(post.dedup_key, now)

    def save(self) -> None:
        # 超過上限時保留最近的鍵,避免檔案無限膨脹
        if len(self._seen) > self.max_keys:
            items = sorted(self._seen.items(), key=lambda kv: kv[1])
            self._seen = dict(items[-self.max_keys :])
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps(self._seen, ensure_ascii=False, indent=0), encoding="utf-8"
        )

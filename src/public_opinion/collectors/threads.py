"""Threads 抓取器(Meta Graph API 關鍵字搜尋)。

需要:
- THREADS_ACCESS_TOKEN(長效 token)
- token 需具備 threads_keyword_search 權限(需向 Meta 申請)

文件:https://developers.facebook.com/docs/threads/keyword-search
未設定 token 時會直接略過。
"""

from __future__ import annotations

import logging
from datetime import datetime

from ..models import Post, parse_iso
from .base import BaseCollector

log = logging.getLogger(__name__)

API = "https://graph.threads.net/v1.0/keyword_search"
FIELDS = "id,text,permalink,timestamp,username"


class ThreadsCollector(BaseCollector):
    name = "threads"

    def collect(self, keywords: list[str], since: datetime) -> list[Post]:
        token = self.config.threads_access_token
        if not token:
            log.warning("[threads] 未設定 THREADS_ACCESS_TOKEN,略過。")
            return []

        search_type = str(self.opts.get("search_type", "TOP"))
        limit = int(self.opts.get("limit", 25))

        posts: list[Post] = []
        seen: set[str] = set()
        for kw in keywords:
            try:
                data = self._get_json(
                    API,
                    params={
                        "q": kw,
                        "search_type": search_type,
                        "fields": FIELDS,
                        "limit": limit,
                        "access_token": token,
                    },
                )
            except Exception as exc:  # noqa: BLE001
                log.warning("[threads] 搜尋「%s」失敗:%s", kw, exc)
                continue

            for item in data.get("data", []):
                pid = str(item.get("id", ""))
                if not pid or pid in seen:
                    continue
                seen.add(pid)
                text = item.get("text", "")
                posts.append(
                    Post(
                        platform="threads",
                        post_id=pid,
                        title=text[:80],
                        content=text[:2000],
                        url=item.get("permalink", ""),
                        author=item.get("username", ""),
                        created_at=parse_iso(item.get("timestamp")),
                        matched_keywords=self._matches(text, keywords) or [kw],
                    )
                )
            self._sleep(1.0)
        return posts

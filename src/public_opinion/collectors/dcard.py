"""Dcard 抓取器(非官方 API)。

使用 https://www.dcard.tw/service/api/v2/search/posts 搜尋。
注意:Dcard 沒有公開 API 政策,且有 Cloudflare 防護,端點可能隨時改版或被擋。
若回傳 403 / 非預期格式,會記錄警告並回傳空清單,不影響其他平台。
"""

from __future__ import annotations

import logging
from datetime import datetime

from ..models import Post, parse_iso
from .base import BaseCollector

log = logging.getLogger(__name__)

SEARCH_URL = "https://www.dcard.tw/service/api/v2/search/posts"


class DcardCollector(BaseCollector):
    name = "dcard"

    def collect(self, keywords: list[str], since: datetime) -> list[Post]:
        limit = int(self.opts.get("limit", 30))
        headers = {
            "Accept": "application/json",
            "Referer": "https://www.dcard.tw/search",
        }

        posts: list[Post] = []
        seen_ids: set[str] = set()
        for kw in keywords:
            try:
                data = self._get_json(
                    SEARCH_URL,
                    params={"query": kw, "limit": limit},
                    headers=headers,
                )
            except Exception as exc:  # noqa: BLE001
                log.warning("[dcard] 搜尋「%s」失敗(可能被擋):%s", kw, exc)
                self.errors.append(f"「{kw}」:{exc}")
                continue

            if not isinstance(data, list):
                log.warning("[dcard] 非預期回傳格式,略過關鍵字「%s」", kw)
                continue

            for item in data:
                pid = str(item.get("id", ""))
                if not pid or pid in seen_ids:
                    continue
                seen_ids.add(pid)
                title = item.get("title", "")
                excerpt = item.get("excerpt", "")
                text = f"{title}\n{excerpt}"
                posts.append(
                    Post(
                        platform="dcard",
                        post_id=pid,
                        title=title,
                        content=excerpt[:2000],
                        url=f"https://www.dcard.tw/f/{item.get('forumAlias', '')}/p/{pid}",
                        author=(item.get("school") or item.get("department") or "匿名"),
                        created_at=parse_iso(item.get("createdAt")),
                        score=int(item.get("likeCount", 0) or 0),
                        num_comments=int(item.get("commentCount", 0) or 0),
                        matched_keywords=self._matches(text, keywords) or [kw],
                        extra={"forum": item.get("forumName", "")},
                    )
                )
            self._sleep(1.0)
        return posts

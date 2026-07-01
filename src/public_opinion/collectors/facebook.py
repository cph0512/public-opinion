"""Facebook 抓取器(Graph API,僅限你管理的粉專)。

重要限制:Facebook 幾年前就關閉了「公開貼文全站關鍵字搜尋」。
因此這裡只能做到:讀取你設定的粉專(page_ids)最近的貼文,再用關鍵字做本地過濾。

需要:
- FACEBOOK_ACCESS_TOKEN(具 pages_read_engagement 權限的粉專 token)
- config 的 facebook.page_ids 指定要監看的粉專

未設定時會略過。
"""

from __future__ import annotations

import logging
from datetime import datetime

from ..models import Post, parse_iso
from .base import BaseCollector

log = logging.getLogger(__name__)

GRAPH = "https://graph.facebook.com/v21.0"
FIELDS = "id,message,permalink_url,created_time,from,reactions.summary(true),comments.summary(true)"


class FacebookCollector(BaseCollector):
    name = "facebook"

    def collect(self, keywords: list[str], since: datetime) -> list[Post]:
        token = self.config.facebook_access_token
        if not token:
            log.warning("[facebook] 未設定 FACEBOOK_ACCESS_TOKEN,略過。")
            return []

        page_ids = self.opts.get("page_ids") or []
        if not page_ids:
            log.warning(
                "[facebook] 未設定 page_ids。Facebook 不開放公開貼文搜尋,"
                "只能監看你管理的粉專;請在 config 填入 page_ids。"
            )
            return []

        limit = int(self.opts.get("limit", 25))
        posts: list[Post] = []
        for page_id in page_ids:
            try:
                data = self._get_json(
                    f"{GRAPH}/{page_id}/posts",
                    params={"fields": FIELDS, "limit": limit, "access_token": token},
                )
            except Exception as exc:  # noqa: BLE001
                log.warning("[facebook] 讀取粉專 %s 失敗:%s", page_id, exc)
                continue

            for item in data.get("data", []):
                message = item.get("message", "")
                matched = self._matches(message, keywords)
                if not matched:
                    continue  # 只保留有命中關鍵字的貼文
                reactions = (item.get("reactions") or {}).get("summary", {})
                comments = (item.get("comments") or {}).get("summary", {})
                posts.append(
                    Post(
                        platform="facebook",
                        post_id=str(item.get("id", "")),
                        title=message[:80],
                        content=message[:2000],
                        url=item.get("permalink_url", ""),
                        author=(item.get("from") or {}).get("name", ""),
                        created_at=parse_iso(item.get("created_time")),
                        score=int(reactions.get("total_count", 0) or 0),
                        num_comments=int(comments.get("total_count", 0) or 0),
                        matched_keywords=matched,
                        extra={"page_id": page_id},
                    )
                )
            self._sleep(1.0)
        return posts

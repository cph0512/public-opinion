"""Reddit 抓取器。

- 若設定了 REDDIT_CLIENT_ID / REDDIT_CLIENT_SECRET,使用官方 OAuth(app-only)較穩定。
- 否則退回公開的 search.json(需帶合理 User-Agent,有速率限制)。
"""

from __future__ import annotations

import logging
from datetime import datetime

from ..models import Post, from_unix
from .base import BaseCollector

log = logging.getLogger(__name__)


class RedditCollector(BaseCollector):
    name = "reddit"

    def collect(self, keywords: list[str], since: datetime) -> list[Post]:
        token = self._get_oauth_token()
        limit = int(self.opts.get("limit", 25))
        sort = str(self.opts.get("sort", "new"))
        subreddits = self.opts.get("subreddits") or []

        posts: list[Post] = []
        query = " OR ".join(f'"{k}"' for k in keywords)

        targets = subreddits if subreddits else [None]
        for sub in targets:
            posts.extend(self._search(query, keywords, limit, sort, sub, token))
            self._sleep(1.0)
        return posts

    def _get_oauth_token(self) -> str | None:
        cid = self.config.reddit_client_id
        secret = self.config.reddit_client_secret
        if not (cid and secret):
            self.errors.append(
                "未設定 REDDIT_CLIENT_ID / REDDIT_CLIENT_SECRET,"
                "改用公開 API(雲端 IP 常被 403 擋)"
            )
            return None
        try:
            resp = self.session.post(
                "https://www.reddit.com/api/v1/access_token",
                data={"grant_type": "client_credentials"},
                auth=(cid, secret),
                timeout=20,
            )
            resp.raise_for_status()
            return resp.json().get("access_token")
        except Exception as exc:  # noqa: BLE001
            log.warning("[reddit] OAuth 失敗,改用公開 API:%s", exc)
            return None

    def _search(self, query, keywords, limit, sort, sub, token) -> list[Post]:
        params = {
            "q": query,
            "sort": sort,
            "limit": limit,
            "t": "day",
            "raw_json": 1,
            "type": "link",
        }
        if token:
            base = "https://oauth.reddit.com"
            headers = {"Authorization": f"Bearer {token}"}
        else:
            base = "https://www.reddit.com"
            headers = None

        if sub:
            url = f"{base}/r/{sub}/search.json"
            params["restrict_sr"] = "true"
        else:
            url = f"{base}/search.json"

        data = self._get_json(url, params=params, headers=headers)
        children = data.get("data", {}).get("children", [])

        posts: list[Post] = []
        for child in children:
            d = child.get("data", {})
            text = f"{d.get('title', '')}\n{d.get('selftext', '')}"
            matched = self._matches(text, keywords)
            permalink = d.get("permalink", "")
            posts.append(
                Post(
                    platform="reddit",
                    post_id=str(d.get("id", "")),
                    title=d.get("title", ""),
                    content=(d.get("selftext", "") or "")[:2000],
                    url=f"https://www.reddit.com{permalink}" if permalink else d.get("url", ""),
                    author=str(d.get("author", "")),
                    created_at=from_unix(d.get("created_utc")),
                    score=int(d.get("score", 0) or 0),
                    num_comments=int(d.get("num_comments", 0) or 0),
                    matched_keywords=matched,
                    extra={"subreddit": d.get("subreddit", "")},
                )
            )
        return posts

"""PTT 抓取器(網頁版 www.ptt.cc)。

PTT 沒有官方 API;這裡用網頁版的「看板內搜尋」(/bbs/{board}/search?q=)
抓文章列表,不需要任何金鑰。部分看板需要 over18=1 cookie(年齡確認)。

文章 ID(M.<unix時間>.A.xxx)內含發文時間,可精準做時間過濾。
"""

from __future__ import annotations

import logging
import re
from datetime import datetime

from bs4 import BeautifulSoup

from ..models import Post, from_unix
from .base import BaseCollector

log = logging.getLogger(__name__)

BASE = "https://www.ptt.cc"
DEFAULT_BOARDS = ["Gossiping", "WomenTalk", "Boy-Girl"]


def _score_from_nrec(nrec: str) -> int:
    """把推文數字串轉成整數:'爆' → 100,'X3' → -30,'12' → 12。"""
    nrec = (nrec or "").strip()
    if not nrec:
        return 0
    if nrec == "爆":
        return 100
    if nrec.startswith("X"):
        rest = nrec[1:]
        return -(int(rest) * 10) if rest.isdigit() else -100
    return int(nrec) if nrec.isdigit() else 0


class PttCollector(BaseCollector):
    name = "ptt"

    def collect(self, keywords: list[str], since: datetime) -> list[Post]:
        boards = self.opts.get("boards") or DEFAULT_BOARDS
        limit = int(self.opts.get("limit", 20))

        posts: list[Post] = []
        seen: set[str] = set()
        for board in boards:
            for kw in keywords:
                try:
                    resp = self.session.get(
                        f"{BASE}/bbs/{board}/search",
                        params={"q": kw, "page": 1},
                        cookies={"over18": "1"},
                        timeout=20,
                    )
                    resp.raise_for_status()
                except Exception as exc:  # noqa: BLE001
                    log.warning("[ptt] %s 搜尋「%s」失敗:%s", board, kw, exc)
                    continue

                parsed = self._parse_list(resp.text, board, kw, keywords)
                for post in parsed[:limit]:
                    if post.post_id in seen:
                        continue
                    seen.add(post.post_id)
                    posts.append(post)
                self._sleep(1.0)
        return posts

    def _parse_list(
        self, html: str, board: str, kw: str, keywords: list[str]
    ) -> list[Post]:
        soup = BeautifulSoup(html, "html.parser")
        out: list[Post] = []
        for ent in soup.select("div.r-ent"):
            link = ent.select_one("div.title a")
            if link is None:  # 已刪除的文章沒有連結
                continue
            href = link.get("href", "")
            title = link.get_text(strip=True)

            m = re.search(r"/(M\.(\d+)\.A\.[0-9A-Fa-f]+)\.html", href)
            article_id = m.group(1) if m else href
            created = from_unix(int(m.group(2))) if m else None

            nrec_el = ent.select_one("div.nrec")
            author_el = ent.select_one("div.author")

            out.append(
                Post(
                    platform="ptt",
                    post_id=f"{board}/{article_id}",
                    title=title,
                    content="",
                    url=f"{BASE}{href}",
                    author=author_el.get_text(strip=True) if author_el else "",
                    created_at=created,
                    score=_score_from_nrec(
                        nrec_el.get_text(strip=True) if nrec_el else ""
                    ),
                    matched_keywords=self._matches(title, keywords) or [kw],
                    extra={"board": board},
                )
            )
        return out

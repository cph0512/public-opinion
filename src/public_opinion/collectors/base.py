"""抓取器基底類別。"""

from __future__ import annotations

import logging
import time
from datetime import datetime, timedelta

import requests

from ..config import Config, PlatformConfig
from ..models import Post, utc_now

log = logging.getLogger(__name__)

USER_AGENT = (
    "public-opinion/0.1 (+https://github.com/cph0512/public-opinion) "
    "personal sentiment monitor"
)


class BaseCollector:
    """所有平台抓取器的共用邏輯。子類別實作 ``collect``。"""

    name: str = "base"

    def __init__(self, config: Config):
        self.config = config
        self.opts: PlatformConfig = config.platform(self.name)
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": USER_AGENT})
        self.errors: list[str] = []  # 本次執行遇到的錯誤(給 UI 顯示用)

    # --- 子類別要實作 ---
    def collect(self, keywords: list[str], since: datetime) -> list[Post]:
        raise NotImplementedError

    # --- 提供給 runner 的統一入口(包好錯誤處理)---
    def run(self, keywords: list[str]) -> list[Post]:
        self.errors = []
        since = utc_now() - timedelta(hours=self.config.since_hours)
        try:
            posts = self.collect(keywords, since)
        except requests.RequestException as exc:
            log.warning("[%s] 網路錯誤:%s", self.name, exc)
            self.errors.append(f"網路錯誤:{exc}")
            return []
        except Exception as exc:  # noqa: BLE001 - 單一平台失敗不應中斷整體
            log.warning("[%s] 抓取失敗:%s", self.name, exc)
            self.errors.append(f"抓取失敗:{exc}")
            return []

        # 時間過濾(有 created_at 才過濾;沒有的保留)
        filtered = [p for p in posts if p.created_at is None or p.created_at >= since]
        log.info("[%s] 取得 %d 筆(過濾後 %d 筆)", self.name, len(posts), len(filtered))
        return filtered

    # --- 小工具 ---
    def _get_json(self, url: str, *, params=None, headers=None, timeout: int = 20):
        resp = self.session.get(url, params=params, headers=headers, timeout=timeout)
        resp.raise_for_status()
        return resp.json()

    @staticmethod
    def _matches(text: str, keywords: list[str]) -> list[str]:
        low = (text or "").lower()
        return [kw for kw in keywords if kw.lower() in low]

    @staticmethod
    def _sleep(seconds: float = 1.0) -> None:
        time.sleep(seconds)

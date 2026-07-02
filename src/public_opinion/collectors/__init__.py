"""各平台抓取器。"""

from __future__ import annotations

from ..config import Config
from .base import BaseCollector
from .reddit import RedditCollector
from .dcard import DcardCollector
from .ptt import PttCollector
from .threads import ThreadsCollector
from .facebook import FacebookCollector

_REGISTRY: dict[str, type[BaseCollector]] = {
    "reddit": RedditCollector,
    "dcard": DcardCollector,
    "ptt": PttCollector,
    "threads": ThreadsCollector,
    "facebook": FacebookCollector,
}


def build_collectors(config: Config) -> list[BaseCollector]:
    """依設定建立已啟用的抓取器。"""
    collectors: list[BaseCollector] = []
    for name, cls in _REGISTRY.items():
        if config.platform(name).enabled:
            collectors.append(cls(config))
    return collectors


__all__ = ["BaseCollector", "build_collectors"]

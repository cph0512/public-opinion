"""設定載入(YAML + 環境變數)。"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


@dataclass
class PlatformConfig:
    enabled: bool = False
    options: dict[str, Any] = field(default_factory=dict)

    def get(self, key: str, default: Any = None) -> Any:
        return self.options.get(key, default)


@dataclass
class Config:
    keywords: list[str] = field(default_factory=list)
    platforms: dict[str, PlatformConfig] = field(default_factory=dict)
    since_hours: int = 24
    min_score: int = 0
    summary_enabled: bool = True
    summary_model: str = "claude-opus-4-8"
    summary_language: str = "zh-TW"
    summary_max_posts: int = 60
    output_dir: str = "reports"
    email_enabled: bool = False
    email_only_when_new: bool = True

    # --- 由環境變數載入的祕密 ---
    anthropic_api_key: str = ""
    reddit_client_id: str = ""
    reddit_client_secret: str = ""
    threads_access_token: str = ""
    facebook_access_token: str = ""
    smtp: dict[str, str] = field(default_factory=dict)

    def platform(self, name: str) -> PlatformConfig:
        return self.platforms.get(name, PlatformConfig())


def _load_dotenv(path: str = ".env") -> None:
    """極簡 .env 載入器(沒有 python-dotenv 也能用)。不覆蓋已存在的環境變數。"""
    p = Path(path)
    if not p.exists():
        return
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key, value = key.strip(), value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def load_config(config_path: str, env_path: str = ".env") -> Config:
    _load_dotenv(env_path)

    raw: dict[str, Any] = {}
    p = Path(config_path)
    if p.exists():
        raw = yaml.safe_load(p.read_text(encoding="utf-8")) or {}

    platforms: dict[str, PlatformConfig] = {}
    for name, opts in (raw.get("platforms") or {}).items():
        opts = dict(opts or {})
        enabled = bool(opts.pop("enabled", False))
        platforms[name] = PlatformConfig(enabled=enabled, options=opts)

    filters = raw.get("filters") or {}
    summary = raw.get("summary") or {}
    output = raw.get("output") or {}
    email = raw.get("email") or {}

    return Config(
        keywords=[str(k) for k in (raw.get("keywords") or []) if str(k).strip()],
        platforms=platforms,
        since_hours=int(filters.get("since_hours", 24)),
        min_score=int(filters.get("min_score", 0)),
        summary_enabled=bool(summary.get("enabled", True)),
        summary_model=str(summary.get("model", "claude-opus-4-8")),
        summary_language=str(summary.get("language", "zh-TW")),
        summary_max_posts=int(summary.get("max_posts", 60)),
        output_dir=str(output.get("dir", "reports")),
        email_enabled=bool(email.get("enabled", False)),
        email_only_when_new=bool(email.get("only_when_new", True)),
        anthropic_api_key=os.environ.get("ANTHROPIC_API_KEY", ""),
        reddit_client_id=os.environ.get("REDDIT_CLIENT_ID", ""),
        reddit_client_secret=os.environ.get("REDDIT_CLIENT_SECRET", ""),
        threads_access_token=os.environ.get("THREADS_ACCESS_TOKEN", ""),
        facebook_access_token=os.environ.get("FACEBOOK_ACCESS_TOKEN", ""),
        smtp={
            "host": os.environ.get("SMTP_HOST", ""),
            "port": os.environ.get("SMTP_PORT", "587"),
            "user": os.environ.get("SMTP_USER", ""),
            "password": os.environ.get("SMTP_PASSWORD", ""),
            "from": os.environ.get("EMAIL_FROM", ""),
            "to": os.environ.get("EMAIL_TO", ""),
        },
    )

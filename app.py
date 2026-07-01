"""FastAPI 版輿情搜尋網頁。

重用 src/public_opinion 的 collectors 與 Config,提供乾淨、可部署到 Cloud Run
的 HTTP 服務。前端用 Tailwind (CDN) + HTMX,無需 build step。
"""

from __future__ import annotations

import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates

REPO_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(REPO_ROOT / "src"))

from public_opinion.analysis.summarizer import generate_summary  # noqa: E402
from public_opinion.collectors import build_collectors  # noqa: E402
from public_opinion.config import Config, PlatformConfig  # noqa: E402
from public_opinion.models import Post  # noqa: E402


PLATFORM_LABELS: dict[str, str] = {
    "reddit": "Reddit",
    "dcard": "Dcard",
    "threads": "Threads",
    "facebook": "Facebook",
}

app = FastAPI(title="輿情搜尋 · public-opinion")
templates = Jinja2Templates(directory=str(REPO_ROOT / "templates"))


def _has_anthropic() -> bool:
    return bool(os.environ.get("ANTHROPIC_API_KEY"))


def _build_config(
    keywords: list[str],
    platforms: list[str],
    hours: int,
    min_score: int,
) -> Config:
    plats: dict[str, PlatformConfig] = {}
    for name in PLATFORM_LABELS:
        opts: dict[str, object] = {}
        if name == "reddit":
            opts = {"limit": 25, "sort": "new", "subreddits": []}
        elif name == "dcard":
            opts = {"limit": 30}
        elif name == "threads":
            opts = {"limit": 25, "search_type": "TOP"}
        elif name == "facebook":
            opts = {"limit": 25, "page_ids": []}
        plats[name] = PlatformConfig(enabled=(name in platforms), options=opts)

    return Config(
        keywords=keywords,
        platforms=plats,
        since_hours=hours,
        min_score=min_score,
        summary_enabled=True,
        summary_language="zh-TW",
        anthropic_api_key=os.environ.get("ANTHROPIC_API_KEY", ""),
        reddit_client_id=os.environ.get("REDDIT_CLIENT_ID", ""),
        reddit_client_secret=os.environ.get("REDDIT_CLIENT_SECRET", ""),
        threads_access_token=os.environ.get("THREADS_ACCESS_TOKEN", ""),
        facebook_access_token=os.environ.get("FACEBOOK_ACCESS_TOKEN", ""),
    )


def _collect(config: Config) -> list[Post]:
    posts: list[Post] = []
    for c in build_collectors(config):
        posts.extend(c.run(config.keywords))
    if config.min_score > 0:
        posts = [p for p in posts if p.score >= config.min_score]
    posts.sort(key=lambda p: p.created_at or datetime.now(timezone.utc), reverse=True)
    return posts


def _parse_keywords(raw: str) -> list[str]:
    return [k.strip() for k in raw.replace(",", ",").split(",") if k.strip()]


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "has_anthropic": _has_anthropic(),
            "platform_labels": PLATFORM_LABELS,
        },
    )


@app.get("/search", response_class=HTMLResponse)
async def search(
    request: Request,
    q: str = Query("", description="關鍵字(逗號分隔)"),
    platforms: list[str] = Query(default_factory=lambda: ["reddit", "dcard"]),
    hours: int = Query(24, ge=1, le=168),
    min_score: int = Query(0, ge=0),
    summary: bool = Query(False),
):
    keywords = _parse_keywords(q)
    ctx: dict[str, object] = {
        "request": request,
        "platform_labels": PLATFORM_LABELS,
        "keywords": keywords,
    }
    if not keywords:
        ctx["error"] = "請至少輸入一個關鍵字。"
        return templates.TemplateResponse("_results.html", ctx)
    if not platforms:
        ctx["error"] = "請至少選擇一個平台。"
        return templates.TemplateResponse("_results.html", ctx)

    config = _build_config(keywords, platforms, hours, min_score)
    posts = _collect(config)

    summary_text: str | None = None
    if summary and _has_anthropic():
        summary_text = generate_summary(posts, config)

    ctx.update({"posts": posts, "summary": summary_text})
    return templates.TemplateResponse("_results.html", ctx)


@app.get("/healthz")
async def healthz():
    return JSONResponse({"ok": True})

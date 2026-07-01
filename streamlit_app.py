"""輿情搜尋 — Streamlit 互動網頁。

重用 src/public_opinion 底下的 build_collectors / Config,讓使用者可以在瀏覽器
輸入關鍵字、選平台、拉時間範圍與分數門檻,即時抓取並顯示各平台貼文。
若偵測到 ANTHROPIC_API_KEY,額外提供 AI 摘要選項。
"""

from __future__ import annotations

import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import streamlit as st

# 讓 `from public_opinion...` 可以匯入 src/ 底下的套件。
_REPO_ROOT = Path(__file__).resolve().parent
_SRC = _REPO_ROOT / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from public_opinion.analysis.summarizer import generate_summary  # noqa: E402
from public_opinion.collectors import build_collectors  # noqa: E402
from public_opinion.config import Config, PlatformConfig  # noqa: E402
from public_opinion.models import Post  # noqa: E402


PLATFORM_LABELS = {
    "reddit": "Reddit",
    "dcard": "Dcard",
    "threads": "Threads",
    "facebook": "Facebook",
}

PLATFORM_COLORS = {
    "reddit": "#FF4500",
    "dcard": "#00B8C4",
    "threads": "#111111",
    "facebook": "#1877F2",
}


def get_secret(name: str, default: str = "") -> str:
    """先讀 st.secrets,再退回環境變數;讀不到就回傳預設值。"""
    try:
        value = st.secrets.get(name)  # type: ignore[attr-defined]
        if value:
            return str(value)
    except (FileNotFoundError, KeyError, AttributeError, Exception):  # noqa: BLE001
        pass
    return os.environ.get(name, default)


def build_runtime_config(
    keywords: list[str],
    selected_platforms: list[str],
    since_hours: int,
    min_score: int,
    summary_language: str = "zh-TW",
) -> Config:
    """依 UI 選項組出一個記憶體內的 Config,不讀 config.yaml。"""
    platforms: dict[str, PlatformConfig] = {}
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
        platforms[name] = PlatformConfig(
            enabled=(name in selected_platforms),
            options=opts,
        )

    return Config(
        keywords=keywords,
        platforms=platforms,
        since_hours=since_hours,
        min_score=min_score,
        summary_enabled=True,
        summary_language=summary_language,
        anthropic_api_key=get_secret("ANTHROPIC_API_KEY"),
        reddit_client_id=get_secret("REDDIT_CLIENT_ID"),
        reddit_client_secret=get_secret("REDDIT_CLIENT_SECRET"),
        threads_access_token=get_secret("THREADS_ACCESS_TOKEN"),
        facebook_access_token=get_secret("FACEBOOK_ACCESS_TOKEN"),
    )


def collect_posts(config: Config) -> list[Post]:
    """跑所有啟用的 collector,回傳合併後的貼文清單。"""
    posts: list[Post] = []
    for collector in build_collectors(config):
        posts.extend(collector.run(config.keywords))
    if config.min_score > 0:
        posts = [p for p in posts if p.score >= config.min_score]
    posts.sort(
        key=lambda p: p.created_at or datetime.now(timezone.utc),
        reverse=True,
    )
    return posts


def render_card(post: Post) -> None:
    color = PLATFORM_COLORS.get(post.platform, "#666")
    label = PLATFORM_LABELS.get(post.platform, post.platform)
    when = (
        post.created_at.astimezone().strftime("%Y-%m-%d %H:%M")
        if post.created_at
        else "時間未知"
    )
    title = (post.title or post.preview or "(無標題)").strip()
    url = post.url or "#"

    st.markdown(
        f"""
        <div style="border:1px solid #e6e6e6; border-radius:10px; padding:14px 16px;
                    margin-bottom:12px; background:#fff;">
          <div style="display:flex; align-items:center; gap:8px; margin-bottom:6px;">
            <span style="background:{color}; color:#fff; padding:2px 8px;
                         border-radius:12px; font-size:12px;">{label}</span>
            <span style="color:#888; font-size:12px;">{when}</span>
            {f'<span style="color:#888; font-size:12px;">· @{post.author}</span>' if post.author else ""}
          </div>
          <div style="font-size:15px; font-weight:600; margin-bottom:6px;">
            <a href="{url}" target="_blank" style="color:#111; text-decoration:none;">{title}</a>
          </div>
          <div style="color:#555; font-size:13px; margin-bottom:8px;">{post.preview}</div>
          <div style="color:#666; font-size:12px;">
            👍 {post.score} · 💬 {post.num_comments}
            {f' · 命中: {"、".join(post.matched_keywords)}' if post.matched_keywords else ""}
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def main() -> None:
    st.set_page_config(
        page_title="輿情搜尋 · public-opinion",
        page_icon="🗞️",
        layout="wide",
    )

    st.title("🗞️ 輿情搜尋")
    st.caption("從 Reddit / Dcard / Threads / Facebook 即時抓取關鍵字相關貼文。")

    has_anthropic = bool(get_secret("ANTHROPIC_API_KEY"))

    with st.sidebar:
        st.header("搜尋條件")
        keywords_raw = st.text_input(
            "關鍵字(可用逗號分隔多個)",
            value="",
            placeholder="例:AI、Claude、電動車",
        )
        selected_platforms = st.multiselect(
            "平台",
            options=list(PLATFORM_LABELS.keys()),
            default=["reddit", "dcard"],
            format_func=lambda x: PLATFORM_LABELS[x],
        )
        since_hours = st.slider("時間範圍(最近幾小時)", 1, 168, 24)
        min_score = st.number_input("最低讚數 / 分數", min_value=0, value=0, step=1)

        if has_anthropic:
            do_summary = st.checkbox("使用 Claude 產生 AI 摘要", value=False)
        else:
            do_summary = False
            st.info("未偵測到 ANTHROPIC_API_KEY,略過 AI 摘要功能。", icon="ℹ️")

        search = st.button("🔎 搜尋", type="primary", use_container_width=True)

    if not search:
        st.info("在左側輸入關鍵字並按「搜尋」開始。", icon="👈")
        return

    keywords = [k.strip() for k in keywords_raw.replace(",", ",").split(",") if k.strip()]
    if not keywords:
        st.warning("請至少輸入一個關鍵字。")
        return
    if not selected_platforms:
        st.warning("請至少選擇一個平台。")
        return

    config = build_runtime_config(
        keywords=keywords,
        selected_platforms=selected_platforms,
        since_hours=int(since_hours),
        min_score=int(min_score),
    )

    with st.spinner("正在抓取各平台貼文……"):
        posts = collect_posts(config)

    st.subheader(f"共 {len(posts)} 筆結果")

    if not posts:
        st.warning("沒有抓到任何貼文,試試放寬時間範圍或換個關鍵字。")
        return

    if do_summary:
        with st.spinner("Claude 正在產生摘要……"):
            summary = generate_summary(posts, config)
        if summary:
            with st.expander("🧠 AI 摘要", expanded=True):
                st.markdown(summary)
        else:
            st.info("這次沒有產出摘要(可能是模型婉拒或設定問題)。", icon="ℹ️")

    tabs = st.tabs(
        [f"全部 ({len(posts)})"]
        + [
            f"{PLATFORM_LABELS[p]} ({sum(1 for x in posts if x.platform == p)})"
            for p in selected_platforms
        ]
    )
    with tabs[0]:
        for post in posts:
            render_card(post)
    for i, plat in enumerate(selected_platforms, start=1):
        with tabs[i]:
            plat_posts = [p for p in posts if p.platform == plat]
            if not plat_posts:
                st.caption("這個平台這次沒抓到符合條件的貼文。")
            for post in plat_posts:
                render_card(post)


if __name__ == "__main__":
    main()

"""輿情搜尋器 — 互動式網頁介面。

在網頁上輸入關鍵字、選擇平台,即時搜尋 Reddit / Dcard(以及設定 token 後的
Threads / Facebook)的相關貼文,並可一鍵用 Claude 產生 AI 摘要。

本機執行:  streamlit run streamlit_app.py
雲端部署:  見 README「部署到 Streamlit Community Cloud」章節(全程用瀏覽器)。
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

# 讓 src/ 底下的 public_opinion 套件可被匯入(不需先 pip install -e .)
sys.path.insert(0, str(Path(__file__).parent / "src"))

import streamlit as st

from public_opinion.analysis.summarizer import generate_summary
from public_opinion.collectors import build_collectors
from public_opinion.config import Config, PlatformConfig

PLATFORM_META = {
    "ptt": ("PTT", "🟢"),
    "reddit": ("Reddit", "🟠"),
    "dcard": ("Dcard", "🔵"),
    "threads": ("Threads", "⚫"),
    "facebook": ("Facebook", "🔷"),
}


def secret(name: str, default: str = "") -> str:
    """優先讀 Streamlit secrets,其次讀環境變數。"""
    try:
        if name in st.secrets:  # type: ignore[operator]
            return str(st.secrets[name])
    except Exception:
        pass
    return os.environ.get(name, default)


st.set_page_config(page_title="輿情搜尋器", page_icon="📡", layout="wide")

st.markdown(
    """
    <style>
      .post-card{border:1px solid #e6e6e6;border-radius:12px;padding:14px 16px;
                 margin-bottom:10px;background:#fff}
      .post-meta{color:#888;font-size:0.85rem;margin-top:4px}
      .badge{display:inline-block;padding:1px 8px;border-radius:999px;
             font-size:0.75rem;background:#f0f2f6;margin-right:6px}
    </style>
    """,
    unsafe_allow_html=True,
)

st.title("📡 輿情搜尋器")
st.caption("輸入你想追蹤的主題,即時搜尋各平台的公開討論。")

# ---------------- 側邊欄:搜尋條件 ----------------
with st.sidebar:
    st.header("搜尋條件")
    kw_raw = st.text_input(
        "關鍵字(可用逗號或空白分隔多個)",
        placeholder="例如:某品牌, 某產品, 某議題",
    )
    platform_labels = st.multiselect(
        "平台",
        options=["PTT", "Reddit", "Dcard", "Threads", "Facebook"],
        default=["PTT", "Reddit", "Dcard"],
        help="PTT 不需金鑰、中文內容多。Reddit 建議設定官方憑證(見下方說明)。"
        "Dcard 為非官方 API,常被 Cloudflare 擋。Threads / Facebook 需要對應 token。",
    )
    ptt_boards_raw = ""
    if "PTT" in platform_labels:
        ptt_boards_raw = st.text_input(
            "PTT 看板(逗號分隔)",
            value=secret("PTT_BOARDS", "Gossiping, WomenTalk, Boy-Girl"),
            help="想搜哪些看板就填哪些,例如:Gossiping, WomenTalk, Boy-Girl, marriage",
        )
    since_hours = st.slider("時間範圍(小時內)", 6, 720, 168, step=6)
    limit = st.slider("每個平台最多筆數", 10, 50, 25, step=5)
    min_score = st.number_input("最低讚數 / 分數", min_value=0, value=0, step=1)

    st.header("AI 摘要")
    has_key = bool(secret("ANTHROPIC_API_KEY"))
    engine_options = ["不使用", "Ollama(本機 / 雲端 Kimi)", "Claude API"]
    default_engine = 2 if has_key else 1
    ai_engine = st.selectbox("摘要引擎", engine_options, index=default_engine)

    ollama_api_key = secret("OLLAMA_API_KEY", "")
    ollama_base_url = secret(
        "OLLAMA_BASE_URL",
        "https://ollama.com" if ollama_api_key else "http://localhost:11434",
    )
    ollama_model = secret("OLLAMA_MODEL", "kimi-k2")
    if ai_engine.startswith("Ollama"):
        ollama_api_key = st.text_input(
            "API Key(Ollama 雲端版)",
            value=ollama_api_key,
            type="password",
            help="用 Ollama Cloud(ollama.com)線上模型時填;跑本機 Ollama 則留空。",
        )
        if ollama_api_key and ollama_base_url == "http://localhost:11434":
            ollama_base_url = "https://ollama.com"
        ollama_base_url = st.text_input(
            "Ollama 位址",
            value=ollama_base_url,
            help="雲端版:https://ollama.com;本機:http://localhost:11434",
        )
        ollama_model = st.text_input(
            "模型名稱",
            value=ollama_model,
            help="填 ollama.com 上的模型名稱(雲端)或 `ollama list` 顯示的名稱(本機)。",
        )
        if ollama_api_key:
            st.caption("☁️ 使用 Ollama Cloud:不需要本機開 Ollama,部署到雲端也能用。")
        else:
            st.caption("💻 本機模式:需要這台電腦的 Ollama 執行中;雲端部署時請改填 API Key。")
    elif ai_engine == "Claude API" and not has_key:
        st.caption("⚠️ 尚未設定 ANTHROPIC_API_KEY(Secrets 或環境變數),摘要會被略過。")

    want_summary = ai_engine != "不使用"

    search = st.button("🔍 搜尋", type="primary", use_container_width=True)


def _build_config(keywords: list[str]) -> Config:
    platforms: dict[str, PlatformConfig] = {}
    fb_pages = [p for p in secret("FACEBOOK_PAGE_IDS", "").split(",") if p.strip()]
    ptt_boards = [b.strip() for b in ptt_boards_raw.split(",") if b.strip()]
    label_to_opts = {
        "PTT": ("ptt", {"limit": limit, "boards": ptt_boards}),
        "Reddit": ("reddit", {"limit": limit, "sort": "relevance"}),
        "Dcard": ("dcard", {"limit": limit}),
        "Threads": ("threads", {"limit": limit}),
        "Facebook": ("facebook", {"limit": limit, "page_ids": fb_pages}),
    }
    for label in platform_labels:
        name, opts = label_to_opts[label]
        platforms[name] = PlatformConfig(enabled=True, options=opts)

    return Config(
        keywords=keywords,
        platforms=platforms,
        since_hours=int(since_hours),
        min_score=int(min_score),
        summary_enabled=want_summary,
        summary_provider="ollama" if ai_engine.startswith("Ollama") else "anthropic",
        summary_model=secret("SUMMARY_MODEL", "claude-opus-4-8"),
        summary_language=secret("SUMMARY_LANGUAGE", "zh-TW"),
        ollama_base_url=ollama_base_url,
        ollama_model=ollama_model,
        ollama_api_key=ollama_api_key,
        anthropic_api_key=secret("ANTHROPIC_API_KEY"),
        reddit_client_id=secret("REDDIT_CLIENT_ID"),
        reddit_client_secret=secret("REDDIT_CLIENT_SECRET"),
        threads_access_token=secret("THREADS_ACCESS_TOKEN"),
        facebook_access_token=secret("FACEBOOK_ACCESS_TOKEN"),
    )


def _render_post(p) -> None:
    label, emoji = PLATFORM_META.get(p.platform, (p.platform, "•"))
    when = p.created_at.strftime("%Y-%m-%d %H:%M") if p.created_at else "—"
    title = (p.title or p.preview or "(無標題)").strip()
    st.markdown(
        f"""
        <div class="post-card">
          <span class="badge">{emoji} {label}</span>
          <a href="{p.url}" target="_blank"><b>{title}</b></a>
          <div class="post-meta">🕒 {when} · 👍 {p.score} · 💬 {p.num_comments}
          {'· 命中:' + '、'.join(p.matched_keywords) if p.matched_keywords else ''}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


# ---------------- 主畫面:執行搜尋 ----------------
if search:
    keywords = [k.strip() for k in kw_raw.replace(",", " ").split() if k.strip()]
    if not keywords:
        st.warning("請先輸入至少一個關鍵字。")
        st.stop()
    if not platform_labels:
        st.warning("請至少選一個平台。")
        st.stop()

    config = _build_config(keywords)

    with st.spinner("搜尋中…"):
        by_platform: dict[str, list] = {}
        for collector in build_collectors(config):
            by_platform[collector.name] = collector.run(keywords)

    all_posts = [p for posts in by_platform.values() for p in posts]
    if min_score > 0:
        all_posts = [p for p in all_posts if p.score >= min_score]
    all_posts.sort(key=lambda p: (p.score, p.num_comments), reverse=True)

    # 各平台筆數摘要
    cols = st.columns(max(len(by_platform), 1))
    for col, (name, posts) in zip(cols, by_platform.items()):
        label, emoji = PLATFORM_META.get(name, (name, "•"))
        note = "(可能被擋)" if not posts and name == "dcard" else ""
        col.metric(f"{emoji} {label}", f"{len(posts)} 筆", help=note or None)

    st.divider()

    if not all_posts:
        st.info("沒有找到符合條件的貼文。可以試著放寬時間範圍、降低最低分數,或換個關鍵字。")
        st.stop()

    # AI 摘要
    if want_summary:
        engine_label = "Ollama" if config.summary_provider == "ollama" else "Claude"
        with st.spinner(f"{engine_label} 產生摘要中…(本機模型可能需要一兩分鐘)"):
            summary = generate_summary(all_posts, config)
        if summary:
            st.subheader(f"🧠 AI 輿情摘要(by {engine_label})")
            st.markdown(summary)
            st.divider()
        else:
            st.warning(
                f"{engine_label} 摘要沒有產生。"
                + (
                    "請確認 Ollama 執行中、模型名稱正確(用 `ollama list` 查)。"
                    if config.summary_provider == "ollama"
                    else "請確認 ANTHROPIC_API_KEY 已設定。"
                )
            )

    st.subheader(f"共 {len(all_posts)} 筆(依熱度排序)")
    for p in all_posts:
        _render_post(p)
else:
    st.info("👈 在左邊輸入關鍵字、選擇平台,然後按「搜尋」。")
    st.caption(
        "提醒:Reddit 最穩定;Dcard 為非官方 API,雲端 IP 有時會被 Cloudflare 擋。"
        "此工具僅供個人輿情觀察,請合理使用並遵守各平台服務條款。"
    )

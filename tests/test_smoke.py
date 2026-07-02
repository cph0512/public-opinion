"""基本 smoke 測試,不需要網路。"""

from __future__ import annotations

from datetime import timezone

from public_opinion.models import Post, from_unix, parse_iso, utc_now
from public_opinion.output.report import build_markdown
from public_opinion.state import SeenStore


def _sample_post(pid: str = "abc") -> Post:
    return Post(
        platform="reddit",
        post_id=pid,
        title="測試標題",
        content="測試內容",
        url="https://example.com/x",
        score=5,
        matched_keywords=["測試"],
        created_at=utc_now(),
    )


def test_dedup_key_stable():
    a, b = _sample_post("x1"), _sample_post("x1")
    assert a.dedup_key == b.dedup_key
    assert a.dedup_key != _sample_post("x2").dedup_key


def test_parse_iso_and_unix():
    assert parse_iso("2024-01-01T00:00:00Z").tzinfo == timezone.utc
    assert parse_iso("bad") is None
    assert from_unix(0).year == 1970
    assert from_unix(None) is None


def test_filter_new(tmp_path):
    store = SeenStore(path=str(tmp_path / "seen.json"))
    posts = [_sample_post("a"), _sample_post("a"), _sample_post("b")]
    fresh = store.filter_new(posts)
    assert len(fresh) == 2  # 同批內去重
    store.mark(fresh)
    store.save()

    store2 = SeenStore(path=str(tmp_path / "seen.json"))
    assert store2.filter_new([_sample_post("a")]) == []  # 跨執行去重


def test_build_markdown_empty():
    md = build_markdown([], ["kw"], None, utc_now())
    assert "輿情日報" in md
    assert "沒有抓到" in md


def test_build_markdown_with_posts():
    md = build_markdown([_sample_post("z")], ["測試"], "摘要內容", utc_now())
    assert "測試標題" in md
    assert "AI 摘要" in md


def test_ollama_summary(monkeypatch):
    """Ollama 後端:模擬 API 回應,確認摘要文字被正確取出。"""
    from public_opinion.analysis import summarizer
    from public_opinion.config import Config

    class FakeResp:
        def raise_for_status(self):
            pass

        def json(self):
            return {"message": {"content": "這是 Kimi 產生的摘要"}}

    captured = {}

    def fake_post(url, json=None, headers=None, timeout=None):
        captured["url"] = url
        captured["model"] = json["model"]
        return FakeResp()

    monkeypatch.setattr(summarizer.requests, "post", fake_post)

    cfg = Config(
        keywords=["測試"],
        summary_enabled=True,
        summary_provider="ollama",
        ollama_base_url="http://localhost:11434",
        ollama_model="kimi-k2",
    )
    out = summarizer.generate_summary([_sample_post("s1")], cfg)
    assert out == "這是 Kimi 產生的摘要"
    assert captured["url"] == "http://localhost:11434/api/chat"
    assert captured["model"] == "kimi-k2"


def test_ollama_summary_connection_error(monkeypatch):
    """Ollama 沒開時應回傳 None,而不是讓流程炸掉。"""
    import requests as _requests
    from public_opinion.analysis import summarizer
    from public_opinion.config import Config

    def fake_post(*a, **k):
        raise _requests.exceptions.ConnectionError("refused")

    monkeypatch.setattr(summarizer.requests, "post", fake_post)
    cfg = Config(keywords=["x"], summary_enabled=True, summary_provider="ollama")
    assert summarizer.generate_summary([_sample_post("s2")], cfg) is None


def test_ollama_cloud_key_header(monkeypatch):
    """有 OLLAMA_API_KEY 時要帶 Bearer header 且能連雲端位址。"""
    from public_opinion.analysis import summarizer
    from public_opinion.config import Config

    class FakeResp:
        def raise_for_status(self):
            pass

        def json(self):
            return {"message": {"content": "雲端 Kimi 摘要"}}

    captured = {}

    def fake_post(url, json=None, headers=None, timeout=None):
        captured["url"] = url
        captured["auth"] = (headers or {}).get("Authorization")
        return FakeResp()

    monkeypatch.setattr(summarizer.requests, "post", fake_post)
    cfg = Config(
        keywords=["x"],
        summary_enabled=True,
        summary_provider="ollama",
        ollama_base_url="https://ollama.com",
        ollama_model="kimi-k2",
        ollama_api_key="ok-test-123",
    )
    out = summarizer.generate_summary([_sample_post("s3")], cfg)
    assert out == "雲端 Kimi 摘要"
    assert captured["url"] == "https://ollama.com/api/chat"
    assert captured["auth"] == "Bearer ok-test-123"


def test_config_ollama_cloud_default(monkeypatch, tmp_path):
    """設定 OLLAMA_API_KEY 且未指定位址時,base_url 應預設為雲端。"""
    from public_opinion.config import load_config

    monkeypatch.setenv("OLLAMA_API_KEY", "ok-abc")
    monkeypatch.delenv("OLLAMA_BASE_URL", raising=False)
    cfg = load_config(str(tmp_path / "none.yaml"), str(tmp_path / "none.env"))
    assert cfg.ollama_base_url == "https://ollama.com"
    assert cfg.ollama_api_key == "ok-abc"


PTT_HTML = """
<div class="r-list-container action-bar-margin bbs-screen">
  <div class="r-ent">
    <div class="nrec"><span class="hl f3">爆</span></div>
    <div class="title">
      <a href="/bbs/WomenTalk/M.1719900000.A.1AB.html">[閒聊] 感情算命到底準不準</a>
    </div>
    <div class="meta">
      <div class="author">alice123</div>
      <div class="date"> 7/02</div>
    </div>
  </div>
  <div class="r-ent">
    <div class="nrec"></div>
    <div class="title">(本文已被刪除)</div>
    <div class="meta"><div class="author">-</div><div class="date"> 7/01</div></div>
  </div>
  <div class="r-ent">
    <div class="nrec"><span class="hl f0">X2</span></div>
    <div class="title">
      <a href="/bbs/WomenTalk/M.1719800000.A.2CD.html">[問卦] 算命的說我明年結婚</a>
    </div>
    <div class="meta">
      <div class="author">bob456</div>
      <div class="date"> 7/01</div>
    </div>
  </div>
</div>
"""


def test_ptt_parse_list():
    from public_opinion.collectors.ptt import PttCollector, _score_from_nrec
    from public_opinion.config import Config, PlatformConfig

    cfg = Config(
        keywords=["算命"],
        platforms={"ptt": PlatformConfig(enabled=True, options={"limit": 20})},
    )
    pc = PttCollector(cfg)
    posts = pc._parse_list(PTT_HTML, "WomenTalk", "算命", ["算命"])

    assert len(posts) == 2  # 被刪除的文章要跳過
    p = posts[0]
    assert p.platform == "ptt"
    assert p.post_id == "WomenTalk/M.1719900000.A.1AB"
    assert p.title == "[閒聊] 感情算命到底準不準"
    assert p.url == "https://www.ptt.cc/bbs/WomenTalk/M.1719900000.A.1AB.html"
    assert p.author == "alice123"
    assert p.score == 100          # 爆
    assert p.created_at is not None and p.created_at.year >= 2024  # 從 ID 取得時間
    assert p.matched_keywords == ["算命"]
    assert posts[1].score == -20   # X2

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

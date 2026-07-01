"""把結果寫成 JSON + Markdown 報告。"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from ..models import Post

PLATFORM_LABEL = {
    "reddit": "Reddit",
    "dcard": "Dcard",
    "threads": "Threads",
    "facebook": "Facebook",
}


def _group_by_platform(posts: list[Post]) -> dict[str, list[Post]]:
    grouped: dict[str, list[Post]] = {}
    for p in posts:
        grouped.setdefault(p.platform, []).append(p)
    for plist in grouped.values():
        plist.sort(key=lambda x: (x.score, x.num_comments), reverse=True)
    return grouped


def build_markdown(
    posts: list[Post], keywords: list[str], summary: str | None, run_time: datetime
) -> str:
    date_str = run_time.strftime("%Y-%m-%d")
    lines: list[str] = [
        f"# 輿情日報 · {date_str}",
        "",
        f"- 關鍵字:{'、'.join(keywords) or '(未設定)'}",
        f"- 新增貼文:**{len(posts)}** 筆",
        f"- 產生時間:{run_time.strftime('%Y-%m-%d %H:%M UTC')}",
        "",
    ]

    if summary:
        lines += ["## 🧠 AI 摘要", "", summary, ""]

    grouped = _group_by_platform(posts)
    if not posts:
        lines += ["_今天沒有抓到新的相關貼文。_", ""]

    for platform, plist in grouped.items():
        label = PLATFORM_LABEL.get(platform, platform)
        lines += [f"## {label}({len(plist)} 筆)", ""]
        for p in plist:
            when = p.created_at.strftime("%m-%d %H:%M") if p.created_at else "—"
            kw = f" · 命中:{'、'.join(p.matched_keywords)}" if p.matched_keywords else ""
            title = (p.title or p.preview).strip() or "(無標題)"
            lines.append(
                f"- [{title}]({p.url})  \n"
                f"  `{when}` · 👍 {p.score} · 💬 {p.num_comments}{kw}"
            )
        lines.append("")

    return "\n".join(lines)


def write_report(
    posts: list[Post],
    keywords: list[str],
    summary: str | None,
    run_time: datetime,
    output_dir: str,
) -> dict[str, str]:
    """寫出 report.json 與 report.md,回傳兩個檔案路徑。"""
    date_str = run_time.strftime("%Y-%m-%d")
    folder = Path(output_dir) / date_str
    folder.mkdir(parents=True, exist_ok=True)

    md = build_markdown(posts, keywords, summary, run_time)
    md_path = folder / "report.md"
    md_path.write_text(md, encoding="utf-8")

    payload = {
        "date": date_str,
        "generated_at": run_time.isoformat(),
        "keywords": keywords,
        "count": len(posts),
        "summary": summary,
        "posts": [p.to_dict() for p in posts],
    }
    json_path = folder / "report.json"
    json_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    return {"markdown": str(md_path), "json": str(json_path)}

"""主流程:抓取 → 過濾 → 去重 → 摘要 → 輸出 → 寄信。"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from .analysis.summarizer import generate_summary
from .collectors import build_collectors
from .config import Config
from .models import Post, utc_now
from .output.emailer import send_email
from .output.report import build_markdown, write_report
from .state import SeenStore

log = logging.getLogger(__name__)


@dataclass
class RunResult:
    total_collected: int
    new_count: int
    files: dict[str, str]
    emailed: bool
    summary: str | None


def run(config: Config, dry_run: bool = False, no_email: bool = False) -> RunResult:
    run_time = utc_now()

    if not config.keywords:
        log.warning("設定裡沒有任何 keywords,無事可做。")
        return RunResult(0, 0, {}, False, None)

    collectors = build_collectors(config)
    if not collectors:
        log.warning("沒有啟用任何平台,請在 config 的 platforms 開啟至少一個。")
        return RunResult(0, 0, {}, False, None)

    # 1. 抓取
    all_posts: list[Post] = []
    for collector in collectors:
        all_posts.extend(collector.run(config.keywords))
    log.info("共抓取 %d 筆(含各平台)。", len(all_posts))

    # 2. 分數過濾
    if config.min_score > 0:
        all_posts = [p for p in all_posts if p.score >= config.min_score]

    # 3. 去重(記住看過的)
    store = SeenStore()
    fresh = store.filter_new(all_posts)
    fresh.sort(key=lambda p: (p.created_at or run_time), reverse=True)
    log.info("去重後新增 %d 筆。", len(fresh))

    # 4. AI 摘要
    summary = generate_summary(fresh, config)

    if dry_run:
        print(build_markdown(fresh, config.keywords, summary, run_time))
        return RunResult(len(all_posts), len(fresh), {}, False, summary)

    # 5. 寫報告
    files = write_report(fresh, config.keywords, summary, run_time, config.output_dir)
    log.info("報告已寫入:%s", files.get("markdown"))

    # 6. 更新去重狀態
    store.mark(fresh)
    store.save()

    # 7. Email
    emailed = False
    should_email = (
        config.email_enabled
        and not no_email
        and (fresh or not config.email_only_when_new)
    )
    if should_email:
        subject = f"[輿情日報] {run_time.strftime('%Y-%m-%d')} · 新增 {len(fresh)} 筆"
        body = build_markdown(fresh, config.keywords, summary, run_time)
        emailed = send_email(subject, body, config)

    return RunResult(len(all_posts), len(fresh), files, emailed, summary)

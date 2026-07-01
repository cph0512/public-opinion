"""命令列入口。"""

from __future__ import annotations

import argparse
import logging
import sys

from .config import load_config
from .runner import run as run_pipeline


def _setup_logging(verbose: bool) -> None:
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="public_opinion", description="每日輿情資訊收集器"
    )
    sub = parser.add_subparsers(dest="command")

    run_p = sub.add_parser("run", help="執行一次收集")
    run_p.add_argument("--config", default="config.yaml", help="設定檔路徑")
    run_p.add_argument("--env", default=".env", help=".env 路徑")
    run_p.add_argument(
        "--dry-run", action="store_true", help="只印出結果,不寫檔、不寄信、不更新去重"
    )
    run_p.add_argument("--no-email", action="store_true", help="這次不寄 Email")
    run_p.add_argument("-v", "--verbose", action="store_true", help="顯示除錯訊息")

    args = parser.parse_args(argv)

    if args.command != "run":
        parser.print_help()
        return 1

    _setup_logging(args.verbose)
    config = load_config(args.config, args.env)
    result = run_pipeline(config, dry_run=args.dry_run, no_email=args.no_email)

    print(
        f"\n完成:抓取 {result.total_collected} 筆,"
        f"新增 {result.new_count} 筆"
        + (f",已寄信" if result.emailed else "")
        + (f",報告 → {result.files.get('markdown')}" if result.files else "")
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())

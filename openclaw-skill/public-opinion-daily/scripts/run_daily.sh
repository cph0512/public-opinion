#!/usr/bin/env bash
# 輿情日報收集腳本 — 自動準備環境並執行收集,最後印出 REPORT_JSON=<路徑>
set -euo pipefail

REPO_DIR="${REPO_DIR:-$HOME/public-opinion}"
REPO_URL="${REPO_URL:-https://github.com/cph0512/public-opinion.git}"

# 1. 取得 / 更新程式碼
if [ ! -d "$REPO_DIR/.git" ]; then
  git clone --depth 1 "$REPO_URL" "$REPO_DIR"
else
  git -C "$REPO_DIR" pull --ff-only >/dev/null 2>&1 || true  # 更新失敗就用現有版本
fi
cd "$REPO_DIR"

# 2. 準備 Python 環境(venv,避開系統 Python 的安裝限制)
if [ ! -x .venv/bin/python ]; then
  python3 -m venv .venv
  .venv/bin/pip install -q requests PyYAML beautifulsoup4
fi

# 3. 首次使用:還沒有 config.yaml → 請 agent 先向使用者要關鍵字
if [ ! -f config.yaml ]; then
  cp config.example.yaml config.yaml
  echo "NEED_KEYWORDS"
  exit 2
fi

# 4. 執行收集(摘要與 email 都關閉 —— 摘要由 agent 撰寫)
PYTHONPATH=src .venv/bin/python -m public_opinion run --config config.yaml --no-email

# 5. 回報今天的報告路徑
TODAY=$(date +%F)
echo "REPORT_JSON=$REPO_DIR/reports/$TODAY/report.json"

# public-opinion — 輿情資訊收集器

每天自動搜尋你關心的 **topic / 關鍵字**,從 **Reddit、Dcard、Threads、Facebook** 抓取相關貼文,
彙整成一份每日報告(JSON + Markdown),並可選擇寄送 Email 摘要到你的信箱。

> 這個專案原本是在 `form-builder` repo 的子資料夾裡開發的(因為當時的權限限制無法直接開新 repo)。
> 下方「搬到獨立 repo」章節有把它變成獨立 `public-opinion` repo 的完整步驟。

---

## 功能

- 🔁 **每日自動執行**:內建 GitHub Actions 排程(cron),不需要自己架伺服器。
- 🔎 **多平台搜尋**:
  - **Reddit** — 官方 / 公開 JSON API,最穩定(建議首選)。
  - **Dcard** — 非官方 JSON API,可用但可能隨時改版失效。
  - **Threads** — Meta Graph API 關鍵字搜尋(需要 access token 與特殊權限)。
  - **Facebook** — Meta 公開貼文搜尋幾乎不開放,僅支援「你自己管理的粉專」貼文過濾。
- 🧠 **AI 摘要(選用)**:設定 `ANTHROPIC_API_KEY` 後,自動用 Claude 產生當日輿情摘要與情緒判讀。
- 🗂️ **去重**:記住看過的貼文,每天只報「新增」的內容。
- 📤 **輸出**:存成檔案(`reports/YYYY-MM-DD/`),並可寄 Email 摘要。

---

## 快速開始(本機)

```bash
# 1. 安裝
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# 2. 建立設定檔
cp config.example.yaml config.yaml
cp .env.example .env
# 編輯 config.yaml 填入你要追蹤的關鍵字;.env 填入 API 金鑰(選用)

# 3. 執行
python -m public_opinion run --config config.yaml
# 只看會抓到什麼、不寄信也不寫檔:
python -m public_opinion run --config config.yaml --dry-run
```

> `PYTHONPATH` 提示:若直接跑 `python -m public_opinion` 找不到套件,先 `pip install -e .`
> 或 `export PYTHONPATH=src`。

---

## 設定(`config.yaml`)

```yaml
keywords:
  - "你的品牌"
  - "某個議題"

platforms:
  reddit:   { enabled: true,  limit: 25, subreddits: [] }   # subreddits 留空 = 全站搜尋
  dcard:    { enabled: true,  limit: 30 }
  threads:  { enabled: false }                               # 需要 Meta token
  facebook: { enabled: false, page_ids: [] }                 # 需要粉專 token

filters:
  since_hours: 24     # 只抓最近 N 小時
  min_score: 0        # 分數/讚數門檻(Reddit 用)

summary:
  enabled: true       # 需要 ANTHROPIC_API_KEY;沒有金鑰會自動跳過
  model: "claude-opus-4-8"
  language: "zh-TW"

output:
  dir: "reports"

email:
  enabled: false      # 設 true 並在 .env 填 SMTP 設定即可寄信
```

金鑰放在環境變數 / `.env`(不要 commit),見 `.env.example`。

---

## 各平台抓取說明與注意事項

| 平台 | 方式 | 需要金鑰? | 備註 |
|------|------|-----------|------|
| Reddit | 公開 `search.json`;有填 `REDDIT_CLIENT_ID/SECRET` 則改用官方 OAuth | 選用 | 最穩定 |
| Dcard | 非官方 `service/api/v2/search/posts` | 否 | 可能被 Cloudflare 擋或改版 |
| Threads | Graph API `keyword_search` | 是(`THREADS_ACCESS_TOKEN`) | 需 `threads_keyword_search` 權限 |
| Facebook | Graph API 粉專貼文 + 本地關鍵字過濾 | 是(`FACEBOOK_ACCESS_TOKEN`) | FB 不開放公開貼文全站搜尋 |

⚠️ **請遵守各平台的服務條款與 robots 政策**,合理設定執行頻率,不要做大量抓取。此工具僅供個人輿情觀察用途。

---

## 每日自動執行(GitHub Actions)

`.github/workflows/daily.yml` 已內建每日 cron。上到 GitHub 後:

1. Repo → **Settings → Secrets and variables → Actions** 新增需要的 secrets:
   - `ANTHROPIC_API_KEY`(AI 摘要,選用)
   - `REDDIT_CLIENT_ID` / `REDDIT_CLIENT_SECRET`(選用)
   - `THREADS_ACCESS_TOKEN` / `FACEBOOK_ACCESS_TOKEN`(對應平台開啟時)
   - Email:`SMTP_HOST` `SMTP_PORT` `SMTP_USER` `SMTP_PASSWORD` `EMAIL_FROM` `EMAIL_TO`
2. 預設每天 UTC 00:00(台灣早上 8 點)執行,並把當天報告 commit 回 repo。
3. 也可到 **Actions** 分頁手動 **Run workflow** 測試。

本機排程(替代方案,crontab):

```cron
0 8 * * * cd /path/to/public-opinion && /path/to/.venv/bin/python -m public_opinion run --config config.yaml
```

---

## 搬到獨立 repo `public-opinion`

這份程式碼目前在 `form-builder/public-opinion/`。要變成你自己的獨立 repo:

```bash
# A. 用 GitHub CLI(最快)
cp -r form-builder/public-opinion ~/public-opinion
cd ~/public-opinion
git init
git add .
git commit -m "init: public opinion collector"
git branch -M main
gh repo create public-opinion --private --source=. --remote=origin --push
# 想公開就把 --private 改成 --public

# B. 或先在 github.com 手動建立空的 public-opinion,再:
cd ~/public-opinion
git init && git add . && git commit -m "init: public opinion collector"
git branch -M main
git remote add origin git@github.com:cph0512/public-opinion.git
git push -u origin main
```

---

## 專案結構

```
public-opinion/
├── src/public_opinion/
│   ├── cli.py            # 命令列入口
│   ├── config.py         # 設定載入
│   ├── models.py         # Post 資料模型
│   ├── runner.py         # 主流程協調
│   ├── state.py          # 去重(記住看過的貼文)
│   ├── collectors/       # 各平台抓取器
│   ├── analysis/         # AI 摘要
│   └── output/           # 報告輸出 + Email
├── .github/workflows/daily.yml
├── config.example.yaml
└── requirements.txt
```

---
name: public-opinion-daily
description: 每日輿情日報 — 搜尋 PTT / Reddit / Dcard 上指定關鍵字的公開討論,彙整成繁體中文日報回報給使用者。當使用者要求「輿情日報」「搜輿情」「今天的輿情」「追蹤某個話題的討論」,或要求排程每日輿情任務時使用本 skill。
---

# 輿情日報(public-opinion-daily)

你(agent)負責執行輿情收集程式、閱讀結果,**親自撰寫**中文日報並傳給使用者。
摘要由你來寫,不呼叫任何外部 AI 服務。

## 執行步驟

1. 執行收集腳本(它會自動準備好一切):

   ```bash
   bash {skill_dir}/scripts/run_daily.sh
   ```

   - 若輸出包含 `NEED_KEYWORDS`:代表第一次使用、還沒設定關鍵字。
     詢問使用者:「你想追蹤哪些關鍵字?(可多個)」,
     然後編輯 `~/public-opinion/config.yaml`,把 `keywords:` 底下改成使用者給的關鍵字
     (YAML 清單格式,每行 `  - "關鍵字"`),再重新執行腳本。
   - 腳本成功時最後一行會印出 `REPORT_JSON=<路徑>`。

2. 讀取那個 `report.json`。結構:`{"date", "keywords", "count", "posts": [...]}`,
   每則 post 有 `platform / title / content / url / score / num_comments / created_at / matched_keywords`。

3. 根據 posts 內容撰寫繁體中文日報,傳給使用者。格式:

   ```
   📡 輿情日報 <date>(新增 <count> 筆)

   【重點】3~5 條條列
   【情緒】正面/中立/負面傾向與大致比例,一句理由
   【值得看的貼文】3~5 則:標題 + 平台 + 連結
   ```

   - `count` 為 0 時:回報「今日無新討論」,不要多寫。
   - **只根據 report.json 撰寫,嚴禁編造貼文、數字或連結。**

## 排程(使用者要求「每天自動」時)

建立每日固定時間的排程任務(使用者沒指定就用 08:00),內容為:執行本 skill 的完整流程並把日報推送給使用者。

## 注意事項

- 程式有跨日去重:每天只會回報「新增」的貼文,`state/` 目錄是去重紀錄,**不要刪改**。
- Reddit 沒設定 `REDDIT_CLIENT_ID/SECRET`(放在 `~/public-opinion/.env`)會被 403 —— 屬正常,略過即可,不用向使用者道歉,只在日報末尾註明「Reddit 未啟用」。
- Dcard 偶爾被 Cloudflare 擋,同樣略過並註明即可。
- 想調整 PTT 看板:編輯 `config.yaml` 裡 `platforms.ptt.boards`。
- 收集腳本對各平台已有 1 秒間隔的禮貌延遲,不要另外平行重複執行本 skill。

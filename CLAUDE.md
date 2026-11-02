# CLAUDE.md

## 專案背景

臺北 YouBike 站點供需預測與缺車預警（求職作品，11/7 – 12/12）。討論方向或寫程式前先讀：

- `docs/01_資料來源與資料定義.md`：即時與歷史資料的網址、欄位定義、實測數字、資料限制
- `docs/03_專題提案報告.md`：目標、技術、時程
- `docs/04_諮詢問題集.md`：還沒定案的決策
- `docs/02_Workflow_用Skills討論專案方向.md`：skills 使用順序與已做過的方向比較

關鍵資料限制（影響設計）：
- 即時 API 只有當下狀態，沒有歷史；`scripts/collect_realtime.py` 負責自己累積到 `data/realtime/`
- 歷史租借紀錄的時間只到整點，只有站名、沒有站點代號（約 99.5% 能對上即時資料的 `sna` 去掉 `YouBike2.0_` 前綴）
- 單月歷史 CSV 約 890 MB，用 DuckDB / Polars，不要用 pandas 一次讀完

## Agent skills

### Issue tracker

Issues and specs live as local markdown files under `.scratch/<feature>/`. See `docs/agents/issue-tracker.md`.

### Triage labels

Uses the five default triage roles as-is (`needs-triage`, `needs-info`, `ready-for-agent`, `ready-for-human`, `wontfix`), recorded as a `Status:` line in each issue file. See `docs/agents/triage-labels.md`.

### Domain docs

Single-context: one `GLOSSARY.md` and `docs/adr/` at the repo root, created lazily. See `docs/agents/domain.md`.

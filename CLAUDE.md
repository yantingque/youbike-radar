# CLAUDE.md

## 專案背景

臺北 YouBike 站點供需預測與缺車預警（求職作品，11/7 – 12/12）。討論方向或寫程式前先讀：

- `docs/superpowers/specs/2026-11-19-youbike-design-v2.md`：**目前的規格書**，包含已定案的決策、模型與評估方式、W1 查到的資料問題、時程。2026-11-02 那份 v1 已被取代
- `docs/01_資料來源與資料定義.md`：即時與歷史資料的網址、欄位定義、實測數字
- `docs/03_專題提案報告.md`：提案報告 v0.2（諮詢後版本）
- `docs/04_諮詢問題集.md`：諮詢紀錄，最上面是 11/09 的結論

設計主軸（細節以規格書為準）：
- 歷史租借紀錄**訓練**「站 × 小時淨流量」迴歸模型；即時資料只當**預測輸入**（現在車數）和**答案**（一小時後的真實車數）
- 預警是規則：`現在車數 + 預測淨流量 ≤ 2`，不另外訓練分類器。對外不用「風險模型」這個詞
- 預測單位是「下一小時」，因為歷史資料只到整點
- 收集器（`ubike/`、`.github/workflows/`、`scripts/collect_local.py`）照常運作，用途是累積對答案用的快照

讀歷史 CSV 的注意事項：
- 單月約 850 MB、760 萬列：整份統計用 DuckDB 直接查 CSV，逐列檢查才抽樣讀進 pandas
- `rent`（騎乘時間）會超過 24 小時，DuckDB 自動判斷成 TIME 會報錯，讀檔時指定 `types={'rent': 'VARCHAR'}`
- 只有站名、沒有站點代號（約 99.5% 能對上即時資料的 `sna` 去掉 `YouBike2.0_` 前綴）

## 教學模式（Colab）

使用者在 Google Colab 自己寫程式，Claude 在對話框一段段教，進度照課程範本 `notebooks/templates/W1_通用範本.ipynb` 的節次走。

每一段的格式：
1. **目的**：這段要回答什麼問題
2. **程式**：完整寫在對話裡。固定的設定直接給完整版；練習的部分留 `____` 讓使用者填，並附提示
3. **要貼回來的東西**：輸出、圖表
4. **判斷問題**：讓使用者用自己的話寫「我的判斷」

使用者說「給答案」才給完整解答。使用者貼回結果後，先說明結果代表什麼，再接下一段。

整理使用者的 notebook（`notebooks/W*_*.ipynb`）時：
- 保留所有程式輸出，只改排版和註解；註解用一行白話說明函數和語法
- 每格輸出下面寫「**看到什麼**」：只寫數字和事實
- 每個需要判斷的地方寫 `**我的判斷：**（提示：要回答的問題）`，後面留空。「我的判斷」由使用者自己寫，Claude 只寫提示問題
- 改完用 `nbformat.validate` 驗證，並確認每格程式的語法正確

`01_專案企劃書_*.docx`（課程繳交用的 Word 檔，已被 `.gitignore` 排除）：改版時另存新版號，舊版保留。

## Agent skills

### Issue tracker

Issues and specs live as local markdown files under `.scratch/<feature>/`. See `docs/agents/issue-tracker.md`.

### Triage labels

Uses the five default triage roles as-is (`needs-triage`, `needs-info`, `ready-for-agent`, `ready-for-human`, `wontfix`), recorded as a `Status:` line in each issue file. See `docs/agents/triage-labels.md`.

### Domain docs

Single-context: one `GLOSSARY.md` and `docs/adr/` at the repo root, created lazily. See `docs/agents/domain.md`.

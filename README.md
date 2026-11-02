# 臺北 YouBike 站點供需預測與缺車預警

用臺北市 YouBike2.0 的即時與歷史開放資料，預測各站 30 分鐘後「借不到車（可借 ≤ 2）」或「還不了車（可還 ≤ 2）」的機率。

- 設計規格：[docs/superpowers/specs/2026-11-02-youbike-design.md](docs/superpowers/specs/2026-11-02-youbike-design.md)
- 資料來源與欄位定義：[docs/01_資料來源與資料定義.md](docs/01_資料來源與資料定義.md)

## 資料收集

官方即時 API 只提供「當下」的站點車數，沒有歷史，所以本專案用 GitHub Actions 自己累積。

| Workflow | 排程 | 做什麼 |
|---|---|---|
| `collect` | 每 10 分鐘 | 抓即時 API，存一份精簡快照到 `data` 分支 |
| `compact` | 每天臺北 00:35 | 把昨天（以及之前錯過）的快照整併成 parquet，更新遺漏率報表 |
| `tests` | push 到 main | 跑 pytest |

### `data` 分支結構

```
stations.csv                              # 站點主檔（站名、行政區、座標、車柱數）
snapshots/raw/YYYY-MM-DD/HHMMSS.csv.gz    # 當天每次收集一檔，整併後刪除
snapshots/YYYY-MM-DD.parquet              # 每日整併結果（每站每 10 分鐘一列）
quality/daily.csv                         # 每日遺漏率
```

快照欄位：`collect_time`（臺北時間）、`sno`、`available_rent_bikes`、`available_return_bikes`、`act`、`mday`，parquet 另有 `slot`（對齊到 10 分鐘格點）與 `mday_ts`（`mday` 解析成時間；格式不符時為空，原始字串仍保留在 `mday`）。單站欄位缺值或無法轉成數字時，只略過那一站。

### 看收集品質

`quality/daily.csv` 每天一列：`received_slots` 是實際收到的 10 分鐘格點數（同一格點收到兩次只算一次），`missing_rate = 1 − received_slots ÷ 144`。目標是每天 < 5%。

### 手動執行

- 到 GitHub repo 的 **Actions** 分頁，選 `collect` 或 `compact`，按 **Run workflow**。
- `compact` 可以填日期（YYYY-MM-DD）重新整併某一天，重跑結果相同。

### 本機備援收集（Windows）

GitHub 排程不穩時，可以讓自己的電腦每 10 分鐘收集一次，並推到同一個 `data` 分支。兩邊同時跑也沒關係，整併時同一個 10 分鐘格點只會留一筆。

```powershell
git worktree add data/datarepo data                                   # 只需做一次
powershell -ExecutionPolicy Bypass -File scripts\register_local_task.ps1
```

- 執行紀錄在 `data/collect_local.log`（只記失敗和每次寫入的快照）。
- 電腦關機或睡眠時不會收集，醒來後會補跑一次。
- 停用：`Unregister-ScheduledTask -TaskName YouBikeCollect -Confirm:$false`

本機執行：

```bash
python -m pip install -r requirements.txt
python -m ubike.collect --out out
python -m ubike.compact --out out --date 2026-11-02
python -m pytest
```

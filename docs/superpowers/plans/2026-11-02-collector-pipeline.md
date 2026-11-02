# 收集管線 實作計畫

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 讓 GitHub Actions 每 10 分鐘收集臺北 YouBike 即時快照（精簡＋壓縮）存到 `data` 分支，並每天整併成 parquet、產出遺漏率報表。

**Architecture:** 一個小 Python 套件 `ubike/`：`snapshot.py`（純轉換函式）、`fetch.py`（抓取＋驗證＋重試）、`collect.py`（每 10 分鐘的 CLI）、`compact.py`（每日整併 CLI）。兩個排程 workflow 先 checkout main 拿程式，再把 `data` 分支 checkout 到子資料夾當輸出目錄，寫完 commit 並 push 回 `data` 分支。

**Tech Stack:** Python 3.11、標準庫 `urllib`／`gzip`／`csv`／`zoneinfo`、polars（parquet）、tzdata、pytest、GitHub Actions。

**Spec:** `docs/superpowers/specs/2026-11-02-youbike-design.md`（本計畫只實作第 3 節元件 ①、① b，以及第 5 節中收集器、每日整併的錯誤處理）

## Global Constraints

- 收集頻率：每 10 分鐘（cron `*/10 * * * *`）；一天應收 **144** 次。
- 快照欄位（只有這些）：`collect_time, sno, available_rent_bikes, available_return_bikes, act, mday`。
- 站點主檔欄位：`sno, sna, sarea, latitude, longitude, Quantity`。
- API：`https://tcgbusfs.blob.core.windows.net/dotapp/youbike/v2/youbike_immediate.json`。
- 異常判定：回傳站數 **< 1,500** 視為失敗；重試 **2** 次（共 3 次嘗試）後仍失敗 → 不寫入任何檔案、程式以非 0 結束。
- 所有時間一律 **Asia/Taipei**，字串格式 `YYYY-MM-DD HH:MM:SS`（不帶時區）。GitHub Actions 主機是 UTC，不可用 `datetime.now()` 不帶時區。
- 遺漏率 ＝ `1 − 實收格點數 ÷ 144`，四捨五入到小數 4 位。
- 分支：程式碼在 `main`；資料只進 `data` 分支（orphan，不含程式碼）。
- repo 必須是 **public**：每 10 分鐘一次約 4,320 次／月，private repo 的免費 Actions 額度（2,000 分鐘）不夠。
- 程式碼註解、commit 訊息、README 用繁體中文。

## Review Focus

1. **時區**：Actions 主機是 UTC，`collect_time` 與檔案日期必須是臺北時間 → Task 1、3 有固定 UTC 時刻的測試。
2. **同一個 10 分鐘格點收到兩次**（cron 延遲後緊接下一次）→ 整併時以 (格點, sno) 去重，只算一個格點 → Task 4 測試。
3. **兩個 workflow 同時 push**（收集與整併、或兩次收集重疊）→ 共用 `concurrency` 群組＋push 前 `git pull --rebase` 重試 3 次 → Task 5 驗證步驟手動連發兩次。
4. **API 回傳不完整**（空陣列、少於 1,500 站、不是 JSON、逾時）→ 不寫半套檔案、非 0 結束 → Task 2、3 測試。
5. **欄位型別不穩**（數字以字串回傳、`act` 是 `"1"`、某站缺 `sno`）→ 轉成 int；缺 `sno` 的站略過 → Task 1 測試。

---

## 檔案結構

```
.gitignore                     # data/、__pycache__/、.venv/、.pytest_cache/、out/
requirements.txt               # polars、tzdata、pytest
pyproject.toml                 # 只放 [tool.pytest.ini_options] pythonpath = ["."]
ubike/__init__.py              # 空
ubike/snapshot.py              # 純函式：精簡欄位、站點主檔、路徑、寫檔
ubike/fetch.py                 # 抓 API、驗證站數、重試
ubike/collect.py               # CLI：抓一次 → 寫 raw 檔＋站點主檔
ubike/compact.py               # CLI：整併某一天 → parquet＋品質報表
tests/test_snapshot.py
tests/test_fetch.py
tests/test_collect.py
tests/test_compact.py
.github/workflows/tests.yml    # push／PR 時跑 pytest
.github/workflows/collect.yml  # 每 10 分鐘
.github/workflows/compact.yml  # 每天 00:30（臺北）
README.md                      # 新增「資料收集」一節
scripts/collect_realtime.py    # 刪除（由 ubike/collect.py 取代）
```

`data` 分支（輸出目錄）的結構：

```
stations.csv                              # 站點主檔，依 sno 排序；內容變了才會產生 commit
snapshots/raw/YYYY-MM-DD/HHMMSS.csv.gz    # 每次收集一檔（整併後刪除）
snapshots/YYYY-MM-DD.parquet              # 每日整併結果
quality/daily.csv                         # date,received_slots,expected_slots,missing_rate,median_stations
```

---

### Task 1: 專案骨架與快照轉換函式

**Files:**
- Create: `.gitignore`, `requirements.txt`, `pyproject.toml`, `ubike/__init__.py`, `ubike/snapshot.py`
- Test: `tests/test_snapshot.py`

**Interfaces:**
- Produces（`ubike/snapshot.py`）：
  - `TAIPEI: ZoneInfo`（`ZoneInfo("Asia/Taipei")`）
  - `SNAPSHOT_FIELDS: list[str]`、`STATION_FIELDS: list[str]`（值見 Global Constraints）
  - `to_taipei(dt: datetime) -> datetime`：帶時區的 datetime 轉臺北時間；不帶時區的拋 `ValueError`
  - `slim_rows(stations: list[dict], collect_time: datetime) -> list[dict]`：每站一列，只含 `SNAPSHOT_FIELDS`；`collect_time` 以臺北時間格式化；三個數字欄轉 `int`；缺 `sno` 或 `sno` 為空的站略過
  - `station_rows(stations: list[dict]) -> list[dict]`：只含 `STATION_FIELDS`，依 `sno` 排序；`Quantity` 轉 `int`、經緯度轉 `float`
  - `raw_path(root: Path, collect_time: datetime) -> Path`：`root/"snapshots"/"raw"/<臺北日期>/<臺北HHMMSS>.csv.gz`
  - `write_raw(rows: list[dict], path: Path) -> None`：gzip 壓縮 CSV（UTF-8、有表頭、欄序 `SNAPSHOT_FIELDS`），自動建資料夾
  - `write_stations(rows: list[dict], path: Path) -> None`：一般 CSV（UTF-8、`\n` 換行、欄序 `STATION_FIELDS`）

- [ ] **Step 1: 初始化 git 與骨架**

```bash
git init -b main
```

`.gitignore` 內容：`data/`、`out/`、`__pycache__/`、`.venv/`、`.pytest_cache/`。`requirements.txt`：`polars>=1.0`、`tzdata`、`pytest>=8`。`pyproject.toml`：

```toml
[tool.pytest.ini_options]
pythonpath = ["."]
testpaths = ["tests"]
```

Run: `python -m pip install -r requirements.txt`
Expected: 安裝成功

- [ ] **Step 2: 寫失敗的測試** `tests/test_snapshot.py`

```python
from datetime import datetime, timezone
from pathlib import Path
import gzip, csv
import pytest
from ubike.snapshot import (slim_rows, station_rows, raw_path, write_raw,
                            to_taipei, SNAPSHOT_FIELDS)

UTC_0735 = datetime(2026, 11, 2, 7, 35, 12, tzinfo=timezone.utc)  # = 臺北 15:35:12

def station(**kw):
    base = {"sno": "500101001", "sna": "YouBike2.0_捷運科技大樓站", "sarea": "大安區",
            "latitude": 25.02605, "longitude": 121.5436, "Quantity": 28,
            "available_rent_bikes": 13, "available_return_bikes": 15,
            "act": "1", "mday": "2026-11-02 15:34:04", "ar": "不要的欄位"}
    base.update(kw)
    return base

def test_slim_rows_keeps_only_snapshot_fields_in_taipei_time():
    rows = slim_rows([station()], UTC_0735)
    assert list(rows[0].keys()) == SNAPSHOT_FIELDS
    assert rows[0]["collect_time"] == "2026-11-02 15:35:12"
    assert rows[0]["act"] == 1

def test_slim_rows_coerces_string_numbers():
    rows = slim_rows([station(available_rent_bikes="7", available_return_bikes="21")], UTC_0735)
    assert rows[0]["available_rent_bikes"] == 7
    assert rows[0]["available_return_bikes"] == 21

def test_slim_rows_skips_station_without_sno():
    rows = slim_rows([station(), station(sno=""), {k: v for k, v in station().items() if k != "sno"}], UTC_0735)
    assert len(rows) == 1

def test_to_taipei_rejects_naive_datetime():
    with pytest.raises(ValueError):
        to_taipei(datetime(2026, 11, 2, 15, 35))

def test_raw_path_uses_taipei_date_across_utc_midnight(tmp_path):
    utc_1630 = datetime(2026, 11, 2, 16, 30, 5, tzinfo=timezone.utc)  # = 臺北 11/03 00:30:05
    assert raw_path(tmp_path, utc_1630) == tmp_path / "snapshots/raw/2026-11-03/003005.csv.gz"

def test_station_rows_sorted_by_sno():
    rows = station_rows([station(sno="500101002"), station(sno="500101001")])
    assert [r["sno"] for r in rows] == ["500101001", "500101002"]
    assert set(rows[0].keys()) == {"sno", "sna", "sarea", "latitude", "longitude", "Quantity"}

def test_write_raw_roundtrip(tmp_path):
    path = tmp_path / "a" / "b.csv.gz"
    write_raw(slim_rows([station()], UTC_0735), path)
    with gzip.open(path, "rt", encoding="utf-8") as f:
        got = list(csv.DictReader(f))
    assert got[0]["sno"] == "500101001" and got[0]["available_rent_bikes"] == "13"
```

- [ ] **Step 3: 跑測試確認失敗**

Run: `python -m pytest tests/test_snapshot.py -v`
Expected: FAIL（`ModuleNotFoundError: No module named 'ubike.snapshot'`）

- [ ] **Step 4: 實作 `ubike/snapshot.py`**（Interfaces 列的全部函式）

- [ ] **Step 5: 跑測試確認通過**

Run: `python -m pytest tests/test_snapshot.py -v`
Expected: 7 passed

- [ ] **Step 6: Commit**

```bash
git add .gitignore requirements.txt pyproject.toml ubike tests docs CLAUDE.md
git commit -m "feat: 快照精簡與站點主檔轉換函式"
```

（第一個 commit 一併收進既有的 `docs/` 與 `CLAUDE.md`；`.docx` 企劃書與 `data/` 不進 repo——`.docx` 是否進版控由使用者決定，預設不加。）

---

### Task 2: 抓取、驗證與重試

**Files:**
- Create: `ubike/fetch.py`
- Test: `tests/test_fetch.py`

**Interfaces:**
- Consumes: 無
- Produces（`ubike/fetch.py`）：
  - `API_URL: str`（Global Constraints 的網址）
  - `class FetchError(Exception)`
  - `validate_stations(data: object, min_count: int = 1500) -> list[dict]`：不是 list、或長度 < `min_count` → 拋 `FetchError`（訊息含實際站數或型別）；否則原樣回傳
  - `fetch_stations(url: str = API_URL, retries: int = 2, timeout: float = 30, backoff: float = 10, opener=urllib.request.urlopen, sleep=time.sleep) -> list[dict]`：每次嘗試＝開網址、`json.load`、`validate_stations`；網路錯誤、JSON 錯誤、`FetchError` 都算失敗；兩次嘗試之間 `sleep(backoff)`；共 `retries + 1` 次都失敗 → 拋 `FetchError`（帶最後一次的原因）

- [ ] **Step 1: 寫失敗的測試** `tests/test_fetch.py`

```python
import io, json
import pytest
from ubike.fetch import fetch_stations, validate_stations, FetchError

def ok_payload(n=1823):
    return json.dumps([{"sno": str(i)} for i in range(n)]).encode()

class FakeOpener:
    """依序回傳 responses；元素是 bytes 就回應，是 Exception 就拋出。"""
    def __init__(self, *responses): self.responses, self.calls = list(responses), 0
    def __call__(self, url, timeout):
        self.calls += 1
        r = self.responses.pop(0)
        if isinstance(r, Exception): raise r
        return io.BytesIO(r)

def test_validate_rejects_too_few_stations():
    with pytest.raises(FetchError, match="1499"):
        validate_stations([{}] * 1499)

def test_validate_rejects_non_list():
    with pytest.raises(FetchError):
        validate_stations({"error": "x"})

def test_fetch_retries_then_succeeds():
    opener = FakeOpener(TimeoutError(), b"not json", ok_payload())
    got = fetch_stations(opener=opener, sleep=lambda s: None)
    assert len(got) == 1823 and opener.calls == 3

def test_fetch_gives_up_after_three_attempts():
    opener = FakeOpener(TimeoutError(), ok_payload(10), b"[]", ok_payload())
    with pytest.raises(FetchError):
        fetch_stations(opener=opener, sleep=lambda s: None)
    assert opener.calls == 3
```

- [ ] **Step 2: 跑測試確認失敗**

Run: `python -m pytest tests/test_fetch.py -v`
Expected: FAIL（`ModuleNotFoundError`）

- [ ] **Step 3: 實作 `ubike/fetch.py`**（`opener(url, timeout=timeout)` 回傳的物件當 context manager 或直接讀都要能用；測試的 `BytesIO` 支援兩者）

- [ ] **Step 4: 跑測試確認通過**

Run: `python -m pytest tests/test_fetch.py -v`
Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
git add ubike/fetch.py tests/test_fetch.py
git commit -m "feat: 抓取即時 API，驗證站數並重試 2 次"
```

---

### Task 3: 收集 CLI

**Files:**
- Create: `ubike/collect.py`
- Delete: `scripts/collect_realtime.py`
- Test: `tests/test_collect.py`

**Interfaces:**
- Consumes: Task 1 的 `slim_rows, station_rows, raw_path, write_raw, write_stations`；Task 2 的 `fetch_stations, FetchError`
- Produces（`ubike/collect.py`）：
  - `collect_once(out: Path, now: datetime, fetch=fetch_stations) -> Path`：抓一次 → 寫 `raw_path(out, now)` 與 `out/"stations.csv"`，回傳 raw 檔路徑；`fetch` 拋錯時直接往上拋，**不寫任何檔案**
  - 與規格書的差異：規格寫「站點主檔每天更新一次」，這裡改成每次都覆寫 `stations.csv`，但內容沒變時 git 不會產生 commit，效果等同「有變才更新」，又不用另外排程
  - `main(argv: list[str] | None = None) -> int`：參數 `--out DIR`（必填）；`now = datetime.now(timezone.utc)`；成功印一行 `<臺北時間> 寫入 <站數> 站 → <路徑>` 回傳 0；`FetchError` 印到 stderr 回傳 1
  - 執行方式：`python -m ubike.collect --out <資料夾>`

- [ ] **Step 1: 寫失敗的測試** `tests/test_collect.py`

```python
from datetime import datetime, timezone
import pytest
from ubike.collect import collect_once, main
from ubike.fetch import FetchError

NOW = datetime(2026, 11, 2, 7, 35, 12, tzinfo=timezone.utc)
STATIONS = [{"sno": f"5001{i:05d}", "sna": "x", "sarea": "大安區", "latitude": 25.0,
             "longitude": 121.5, "Quantity": 20, "available_rent_bikes": 5,
             "available_return_bikes": 15, "act": "1", "mday": "2026-11-02 15:34:04"}
            for i in range(1600)]

def test_collect_once_writes_raw_and_stations(tmp_path):
    path = collect_once(tmp_path, NOW, fetch=lambda: STATIONS)
    assert path == tmp_path / "snapshots/raw/2026-11-02/153512.csv.gz"
    assert path.exists() and (tmp_path / "stations.csv").exists()

def test_collect_once_writes_nothing_when_fetch_fails(tmp_path):
    def boom(): raise FetchError("1499 站")
    with pytest.raises(FetchError):
        collect_once(tmp_path, NOW, fetch=boom)
    assert list(tmp_path.rglob("*")) == []

def test_main_returns_1_on_fetch_error(tmp_path, monkeypatch):
    def boom(*a, **k): raise FetchError("逾時")
    monkeypatch.setattr("ubike.collect.fetch_stations", boom)
    assert main(["--out", str(tmp_path)]) == 1
```

（`collect_once` 的 `fetch` 預設值要在呼叫時才查 `fetch_stations`，例如 `fetch=None` 再於函式內取模組層的 `fetch_stations`，`monkeypatch` 才會生效。）

- [ ] **Step 2: 跑測試確認失敗**

Run: `python -m pytest tests/test_collect.py -v`
Expected: FAIL（`ModuleNotFoundError`）

- [ ] **Step 3: 實作 `ubike/collect.py`，並刪除 `scripts/collect_realtime.py`**

- [ ] **Step 4: 跑全部測試確認通過**

Run: `python -m pytest -v`
Expected: 14 passed

- [ ] **Step 5: 真實 API 冒煙測試**

Run: `python -m ubike.collect --out out`
Expected: 印出 `2026-11-.. ..:..:.. 寫入 18xx 站 → out\snapshots\raw\...csv.gz`，且 `out/stations.csv` 存在（`out/` 已在 `.gitignore`）

- [ ] **Step 6: Commit**

```bash
git add ubike/collect.py tests/test_collect.py
git rm scripts/collect_realtime.py
git commit -m "feat: 收集 CLI，取代舊的 collect_realtime.py"
```

---

### Task 4: 每日整併與品質報表

**Files:**
- Create: `ubike/compact.py`
- Test: `tests/test_compact.py`

**Interfaces:**
- Consumes: Task 1 的 `TAIPEI`, `write_raw`（只在測試裡造資料）
- Produces（`ubike/compact.py`）：
  - `EXPECTED_SLOTS = 144`
  - `slot_of(ts: datetime) -> datetime`：往下取整到 10 分鐘（`15:39:59 → 15:30:00`）
  - `compact_day(root: Path, day: date) -> dict`：
    1. 讀 `root/snapshots/raw/<day>/*.csv.gz`，若 `root/snapshots/<day>.parquet` 已存在也一併讀入（讓重跑結果一樣；既有 parquet 先丟掉 `slot` 欄，型別已是步驟 2 的型別，raw 轉完型別後再合併）
    2. 型別：`collect_time`、`mday` → Datetime（格式 `%Y-%m-%d %H:%M:%S`，`mday` 解析失敗給 null）；`sno` → 字串；三個數字欄 → Int16（`act` 用 Int8）
    3. 新增 `slot` 欄＝`slot_of(collect_time)`；以 (`slot`, `sno`) 去重，保留 `collect_time` 最早的那筆
    4. 有資料 → 寫 `root/snapshots/<day>.parquet`（依 `slot, sno` 排序），寫成功後刪除 `raw/<day>/` 資料夾
    5. 回傳品質列 `{"date": "YYYY-MM-DD", "received_slots": int, "expected_slots": 144, "missing_rate": float, "median_stations": int}`；完全沒資料時 `received_slots=0, missing_rate=1.0, median_stations=0`，不寫 parquet、不拋錯
  - `upsert_quality(path: Path, row: dict) -> None`：`quality/daily.csv` 中同 `date` 的列取代，否則附加；依 `date` 排序；檔案不存在就建立（含表頭）
  - `main(argv: list[str] | None = None) -> int`：`--out DIR`（必填）、`--date YYYY-MM-DD`（預設＝臺北時間的昨天）；印出品質列；回傳 0
  - 執行方式：`python -m ubike.compact --out <資料夾> [--date 2026-11-02]`

- [ ] **Step 1: 寫失敗的測試** `tests/test_compact.py`

```python
from datetime import date, datetime
import polars as pl
from ubike.compact import compact_day, slot_of, upsert_quality
from ubike.snapshot import write_raw

DAY = date(2026, 11, 2)

def put(root, hhmmss, snos=("A", "B")):
    t = f"2026-11-02 {hhmmss[:2]}:{hhmmss[2:4]}:{hhmmss[4:]}"
    rows = [{"collect_time": t, "sno": s, "available_rent_bikes": 3,
             "available_return_bikes": 9, "act": 1, "mday": "壞掉的時間"} for s in snos]
    write_raw(rows, root / "snapshots/raw/2026-11-02" / f"{hhmmss}.csv.gz")

def test_slot_of_floors_to_ten_minutes():
    assert slot_of(datetime(2026, 11, 2, 15, 39, 59)) == datetime(2026, 11, 2, 15, 30)

def test_two_runs_in_same_slot_count_once(tmp_path):
    put(tmp_path, "153005"); put(tmp_path, "153812"); put(tmp_path, "154001")
    q = compact_day(tmp_path, DAY)
    assert q["received_slots"] == 2
    assert q["missing_rate"] == round(1 - 2 / 144, 4)
    df = pl.read_parquet(tmp_path / "snapshots/2026-11-02.parquet")
    assert df.height == 4  # 2 格點 × 2 站
    assert df.filter(pl.col("slot") == datetime(2026, 11, 2, 15, 30))["collect_time"].min() == datetime(2026, 11, 2, 15, 30, 5)
    assert df["mday"].null_count() == 4

def test_raw_folder_removed_after_compaction(tmp_path):
    put(tmp_path, "153005")
    compact_day(tmp_path, DAY)
    assert not (tmp_path / "snapshots/raw/2026-11-02").exists()

def test_rerun_is_idempotent(tmp_path):
    put(tmp_path, "153005")
    first = compact_day(tmp_path, DAY)
    assert compact_day(tmp_path, DAY) == first

def test_empty_day_reports_full_missing(tmp_path):
    q = compact_day(tmp_path, DAY)
    assert q["received_slots"] == 0 and q["missing_rate"] == 1.0
    assert not (tmp_path / "snapshots/2026-11-02.parquet").exists()

def test_upsert_quality_replaces_same_date(tmp_path):
    p = tmp_path / "quality/daily.csv"
    base = {"expected_slots": 144, "median_stations": 1823}
    upsert_quality(p, {"date": "2026-11-03", "received_slots": 140, "missing_rate": 0.0278, **base})
    upsert_quality(p, {"date": "2026-11-02", "received_slots": 100, "missing_rate": 0.3056, **base})
    upsert_quality(p, {"date": "2026-11-02", "received_slots": 144, "missing_rate": 0.0, **base})
    df = pl.read_csv(p)
    assert df["date"].to_list() == ["2026-11-02", "2026-11-03"]
    assert df["received_slots"].to_list() == [144, 140]
```

- [ ] **Step 2: 跑測試確認失敗**

Run: `python -m pytest tests/test_compact.py -v`
Expected: FAIL（`ModuleNotFoundError`）

- [ ] **Step 3: 實作 `ubike/compact.py`**（讀 gzip CSV 用 `pl.read_csv(gzip.open(p).read(), schema_overrides=...)`，確保 `sno` 讀成字串）

- [ ] **Step 4: 跑全部測試確認通過**

Run: `python -m pytest -v`
Expected: 20 passed

- [ ] **Step 5: 用 Task 3 冒煙測試產生的資料試跑**

Run: `python -m ubike.compact --out out --date <Task 3 冒煙測試那天>`
Expected: 印出 `received_slots` ≥ 1 的品質列；`out/snapshots/<日期>.parquet` 與 `out/quality/daily.csv` 存在，`out/snapshots/raw/<日期>/` 已刪除

- [ ] **Step 6: Commit**

```bash
git add ubike/compact.py tests/test_compact.py
git commit -m "feat: 每日整併成 parquet 並產出遺漏率報表"
```

---

### Task 5: GitHub Actions 工作流程

**Files:**
- Create: `.github/workflows/tests.yml`, `.github/workflows/collect.yml`, `.github/workflows/compact.yml`
- Modify: `README.md`（不存在就建立）新增「資料收集」一節

**Interfaces:**
- Consumes: `python -m ubike.collect --out datarepo`、`python -m ubike.compact --out datarepo`
- Produces: `data` 分支上的檔案（結構見「檔案結構」）

三個 workflow 的共同規則：

| 項目 | 值 |
|---|---|
| Python | `actions/setup-python` 3.11，`cache: pip`，`pip install -r requirements.txt` |
| tests.yml 觸發 | `push`、`pull_request` 到 `main`；執行 `python -m pytest -v` |
| collect.yml 觸發 | `schedule: cron "*/10 * * * *"`＋`workflow_dispatch` |
| compact.yml 觸發 | `schedule: cron "30 16 * * *"`（＝臺北 00:30）＋`workflow_dispatch`（可選填 `date` 輸入，傳給 `--date`） |
| 權限 | `permissions: contents: write`（collect、compact） |
| 併發 | collect 與 compact 都設 `concurrency: { group: data-branch, cancel-in-progress: false }` |
| checkout | 第一個 `actions/checkout`（main，程式）；第二個 `actions/checkout` 帶 `ref: data`、`path: datarepo` |
| commit 身分 | `github-actions[bot]` / `41898283+github-actions[bot]@users.noreply.github.com` |
| commit 訊息 | collect：`data: 快照 <臺北時間>`；compact：`data: 整併 <日期>` |
| 沒有變更 | `git diff --cached --quiet` 成立就跳過 commit（例如收集失敗時） |
| push | `git pull --rebase origin data` 後 `git push`，失敗重試最多 3 次、間隔 5 秒 |

collect.yml 的收集步驟失敗（非 0）時，整個 job 失敗讓 GitHub 寄通知信；commit／push 步驟只在收集成功時執行。

- [ ] **Step 1: 寫三個 workflow 檔**（照上表）

- [ ] **Step 2: 本機檢查 YAML 能解析**

Run: `python -c "import yaml,glob;[yaml.safe_load(open(f,encoding='utf-8')) for f in glob.glob('.github/workflows/*.yml')];print('ok')"`
Expected: `ok`（沒有 `yaml` 就先 `python -m pip install pyyaml`，不寫進 requirements）

- [ ] **Step 3: README「資料收集」一節**：說明兩個排程、`data` 分支結構、怎麼看 `quality/daily.csv`、怎麼手動觸發

- [ ] **Step 4: Commit**

```bash
git add .github README.md
git commit -m "ci: 每 10 分鐘收集與每日整併的 GitHub Actions"
```

---

### Task 6: 上線與驗收（含使用者操作）

**Files:** 無新檔案

- [ ] **Step 1（使用者）: 在 github.com 建立 public repo**（例如 `youbike-radar`，不要勾選初始化 README），把網址貼給 agent

- [ ] **Step 2: 推 main 並建立 orphan `data` 分支**

```bash
git remote add origin <repo 網址>
git push -u origin main
git switch --orphan data
git commit --allow-empty -m "data: 初始化資料分支"
git push -u origin data
git switch main
```

Expected: GitHub 上看得到 `main`、`data` 兩個分支；`tests` workflow 在 main 上綠燈

- [ ] **Step 3（使用者）: 到 repo 的 Actions 分頁手動執行一次 `collect`**（Run workflow）

Expected: 成功；`data` 分支出現 `stations.csv` 與 `snapshots/raw/<今天>/<時間>.csv.gz`

- [ ] **Step 4: 驗證併發**：使用者連按兩次 `collect` 的 Run workflow

Expected: 兩次都成功（第二次排隊等第一次），`data` 分支多兩個 raw 檔，沒有 push 失敗

- [ ] **Step 5: 等 1 小時後檢查排程**

Expected: `data` 分支在這 1 小時內有 ≥ 4 個新的 raw 檔（cron 常延遲，6 個是理想值）

- [ ] **Step 6: 隔天 00:30 後檢查整併**

Expected: `data` 分支有 `snapshots/<昨天>.parquet`、`quality/daily.csv` 有昨天那一列、`snapshots/raw/<昨天>/` 已消失。上線第一天不滿 24 小時，遺漏率偏高是正常的；從第二個完整日開始對照 < 5% 的驗收標準。

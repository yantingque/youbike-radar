"""快照的純轉換函式：精簡欄位、站點主檔、檔案路徑、寫檔。

所有時間一律轉成臺北時間；GitHub Actions 主機是 UTC，所以不接受不帶時區的 datetime。
"""
import csv
import gzip
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

TAIPEI = ZoneInfo("Asia/Taipei")
TIME_FMT = "%Y-%m-%d %H:%M:%S"

SNAPSHOT_FIELDS = [
    "collect_time",
    "sno",
    "available_rent_bikes",
    "available_return_bikes",
    "act",
    "mday",
]
STATION_FIELDS = ["sno", "sna", "sarea", "latitude", "longitude", "Quantity"]


def to_taipei(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        raise ValueError("需要帶時區的 datetime，避免把 UTC 誤當臺北時間")
    return dt.astimezone(TAIPEI)


def _num(value, cast):
    """轉成數字；None、空字串、亂碼回傳 None，讓呼叫端略過該站而不是整輪失敗。"""
    try:
        return cast(value)
    except (TypeError, ValueError):
        return None


def slim_rows(stations: list[dict], collect_time: datetime) -> list[dict]:
    stamp = to_taipei(collect_time).strftime(TIME_FMT)
    rows = []
    for s in stations:
        sno = str(s.get("sno") or "").strip()
        nums = {k: _num(s.get(k), int) for k in ("available_rent_bikes", "available_return_bikes", "act")}
        if not sno or None in nums.values():
            continue  # 單站壞資料只丟那一站
        rows.append({"collect_time": stamp, "sno": sno, **nums, "mday": s.get("mday", "")})
    return rows


def station_rows(stations: list[dict]) -> list[dict]:
    rows = []
    for s in stations:
        sno = str(s.get("sno") or "").strip()
        lat, lng = _num(s.get("latitude"), float), _num(s.get("longitude"), float)
        qty = _num(s.get("Quantity"), int)
        if not sno or None in (lat, lng, qty):
            continue
        rows.append({"sno": sno, "sna": s.get("sna", ""), "sarea": s.get("sarea", ""),
                     "latitude": lat, "longitude": lng, "Quantity": qty})
    return sorted(rows, key=lambda r: r["sno"])


def raw_path(root: Path, collect_time: datetime) -> Path:
    t = to_taipei(collect_time)
    return root / "snapshots" / "raw" / t.strftime("%Y-%m-%d") / f"{t.strftime('%H%M%S')}.csv.gz"


def write_raw(rows: list[dict], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(path, "wt", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=SNAPSHOT_FIELDS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def write_stations(rows: list[dict], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=STATION_FIELDS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)

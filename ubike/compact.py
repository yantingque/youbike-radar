"""把某一天的 raw 快照整併成一個 parquet，並記錄當天遺漏率。

用法：python -m ubike.compact --out <資料夾> [--date YYYY-MM-DD]
不給 --date 時整併臺北時間的「昨天」。可以重跑，結果相同。
"""
import argparse
import csv
import gzip
import shutil
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

import polars as pl

from ubike.snapshot import TAIPEI, TIME_FMT

EXPECTED_SLOTS = 144  # 每 10 分鐘一次
QUALITY_FIELDS = ["date", "received_slots", "expected_slots", "missing_rate", "median_stations"]

RAW_SCHEMA = {
    "collect_time": pl.String,
    "sno": pl.String,
    "available_rent_bikes": pl.Int16,
    "available_return_bikes": pl.Int16,
    "act": pl.Int8,
    "mday": pl.String,
}


def slot_of(ts: datetime) -> datetime:
    return ts.replace(minute=ts.minute - ts.minute % 10, second=0, microsecond=0)


def _read_raw(path: Path) -> pl.DataFrame:
    with gzip.open(path, "rb") as f:
        df = pl.read_csv(f.read(), schema_overrides=RAW_SCHEMA)
    return df.with_columns(
        pl.col("collect_time").str.to_datetime(TIME_FMT),
        pl.col("mday").str.to_datetime(TIME_FMT, strict=False),  # 解析失敗給 null
    )


def compact_day(root: Path, day: date) -> dict:
    day_str = day.isoformat()
    raw_dir = root / "snapshots" / "raw" / day_str
    out_path = root / "snapshots" / f"{day_str}.parquet"

    frames = [_read_raw(p) for p in sorted(raw_dir.glob("*.csv.gz"))]
    if out_path.exists():
        frames.append(pl.read_parquet(out_path).drop("slot"))

    if not frames:
        return {"date": day_str, "received_slots": 0, "expected_slots": EXPECTED_SLOTS,
                "missing_rate": 1.0, "median_stations": 0}

    df = (
        pl.concat(frames)
        .with_columns(pl.col("collect_time").dt.truncate("10m").alias("slot"))
        .sort("collect_time")
        .unique(subset=["slot", "sno"], keep="first", maintain_order=True)
        .sort(["slot", "sno"])
    )
    out_path.parent.mkdir(parents=True, exist_ok=True)
    df.write_parquet(out_path)
    if raw_dir.exists():
        shutil.rmtree(raw_dir)

    per_slot = df.group_by("slot").len()
    received = per_slot.height
    return {
        "date": day_str,
        "received_slots": received,
        "expected_slots": EXPECTED_SLOTS,
        "missing_rate": round(1 - received / EXPECTED_SLOTS, 4),
        "median_stations": int(per_slot["len"].median()),
    }


def upsert_quality(path: Path, row: dict) -> None:
    rows = {}
    if path.exists():
        with path.open(encoding="utf-8", newline="") as f:
            rows = {r["date"]: r for r in csv.DictReader(f)}
    rows[row["date"]] = row
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=QUALITY_FIELDS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows[d] for d in sorted(rows))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="整併某一天的快照並記錄遺漏率")
    parser.add_argument("--out", required=True, type=Path, help="資料夾（data 分支）")
    parser.add_argument("--date", type=date.fromisoformat, help="YYYY-MM-DD，預設臺北時間昨天")
    args = parser.parse_args(argv)

    day = args.date or (datetime.now(TAIPEI).date() - timedelta(days=1))
    row = compact_day(args.out, day)
    upsert_quality(args.out / "quality" / "daily.csv", row)
    print(row)
    return 0


if __name__ == "__main__":
    sys.exit(main())

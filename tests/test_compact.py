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
    first_slot = df.filter(pl.col("slot") == datetime(2026, 11, 2, 15, 30))
    assert first_slot["collect_time"].min() == datetime(2026, 11, 2, 15, 30, 5)
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

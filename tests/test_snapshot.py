import csv
import gzip
from datetime import datetime, timezone

import pytest

from ubike.snapshot import (
    SNAPSHOT_FIELDS,
    raw_path,
    slim_rows,
    station_rows,
    to_taipei,
    write_raw,
    write_stations,
)

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
    no_sno = {k: v for k, v in station().items() if k != "sno"}
    rows = slim_rows([station(), station(sno=""), no_sno], UTC_0735)
    assert len(rows) == 1


def test_slim_rows_skips_station_with_unparseable_numbers():
    no_act = {k: v for k, v in station().items() if k != "act"}
    bad = [station(sno="2", available_rent_bikes=None), no_act,
           station(sno="3", available_return_bikes="")]
    rows = slim_rows([station()] + bad, UTC_0735)
    assert [r["sno"] for r in rows] == ["500101001"]


def test_station_rows_skips_station_with_bad_coordinates():
    rows = station_rows([station(), station(sno="2", latitude=None), station(sno="3", Quantity="")])
    assert [r["sno"] for r in rows] == ["500101001"]


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


def test_write_stations_has_utf8_bom_so_excel_shows_chinese(tmp_path):
    path = tmp_path / "stations.csv"
    write_stations(station_rows([station(sno="500101001", sna="YouBike2.0_捷運科技大樓站")]), path)
    assert path.read_bytes().startswith(b"\xef\xbb\xbf")
    with path.open(encoding="utf-8-sig", newline="") as f:
        row = next(csv.DictReader(f))
    assert row["sno"] == "500101001"
    assert row["sna"] == "YouBike2.0_捷運科技大樓站"

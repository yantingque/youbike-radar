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
    def boom():
        raise FetchError("1499 站")
    with pytest.raises(FetchError):
        collect_once(tmp_path, NOW, fetch=boom)
    assert list(tmp_path.rglob("*")) == []


def test_main_returns_1_on_fetch_error(tmp_path, monkeypatch):
    def boom(*a, **k):
        raise FetchError("逾時")
    monkeypatch.setattr("ubike.collect.fetch_stations", boom)
    assert main(["--out", str(tmp_path)]) == 1

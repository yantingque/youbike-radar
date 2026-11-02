"""抓一次即時資料，寫成精簡快照（raw）並更新站點主檔。

用法：python -m ubike.collect --out <資料夾>
GitHub Actions 每 10 分鐘執行一次，<資料夾> 是 checkout 下來的 data 分支。
"""
import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

from ubike.fetch import FetchError, fetch_stations
from ubike.snapshot import TIME_FMT, raw_path, slim_rows, station_rows, to_taipei, write_raw, write_stations


def collect_once(out: Path, now: datetime, fetch=None) -> Path:
    # 執行時才查 fetch_stations，測試才能用 monkeypatch 換掉
    stations = (fetch or fetch_stations)()  # 失敗直接往上拋，此時還沒寫任何檔案
    path = raw_path(out, now)
    write_raw(slim_rows(stations, now), path)
    write_stations(station_rows(stations), out / "stations.csv")
    return path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="收集一次 YouBike 即時快照")
    parser.add_argument("--out", required=True, type=Path, help="輸出資料夾（data 分支）")
    args = parser.parse_args(argv)

    now = datetime.now(timezone.utc)
    try:
        path = collect_once(args.out, now)
    except FetchError as e:
        print(f"收集失敗：{e}", file=sys.stderr)
        return 1
    print(f"{to_taipei(now).strftime(TIME_FMT)} 寫入快照 → {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

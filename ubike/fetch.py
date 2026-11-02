"""抓臺北 YouBike2.0 即時 API，檢查站數，失敗就重試。"""
import json
import time
import urllib.request

API_URL = "https://tcgbusfs.blob.core.windows.net/dotapp/youbike/v2/youbike_immediate.json"


class FetchError(Exception):
    pass


def validate_stations(data: object, min_count: int = 1500) -> list[dict]:
    if not isinstance(data, list):
        raise FetchError(f"回傳格式不是陣列：{type(data).__name__}")
    if len(data) < min_count:
        raise FetchError(f"站數只有 {len(data)}，少於 {min_count}")
    return data


def fetch_stations(
    url: str = API_URL,
    retries: int = 2,
    timeout: float = 30,
    backoff: float = 10,
    opener=urllib.request.urlopen,
    sleep=time.sleep,
) -> list[dict]:
    last_error: Exception | None = None
    for attempt in range(retries + 1):
        if attempt:
            sleep(backoff)
        try:
            with opener(url, timeout=timeout) as resp:
                return validate_stations(json.load(resp))
        except (OSError, ValueError, FetchError) as e:  # 網路錯誤／逾時、JSON 錯誤、站數不足
            last_error = e
    raise FetchError(f"嘗試 {retries + 1} 次都失敗：{last_error}") from last_error

import io
import json

import pytest

from ubike.fetch import FetchError, fetch_stations, validate_stations


def ok_payload(n=1823):
    return json.dumps([{"sno": str(i)} for i in range(n)]).encode()


class FakeOpener:
    """依序回傳 responses；元素是 bytes 就回應，是 Exception 就拋出。"""

    def __init__(self, *responses):
        self.responses, self.calls = list(responses), 0

    def __call__(self, url, timeout):
        self.calls += 1
        r = self.responses.pop(0)
        if isinstance(r, Exception):
            raise r
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


def test_fetch_retries_incomplete_read():
    import http.client
    opener = FakeOpener(http.client.IncompleteRead(b"[{"), ok_payload())
    got = fetch_stations(opener=opener, sleep=lambda s: None)
    assert len(got) == 1823 and opener.calls == 2


def test_fetch_gives_up_after_three_attempts():
    opener = FakeOpener(TimeoutError(), ok_payload(10), b"[]", ok_payload())
    with pytest.raises(FetchError):
        fetch_stations(opener=opener, sleep=lambda s: None)
    assert opener.calls == 3

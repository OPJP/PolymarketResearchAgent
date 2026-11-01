import json
from pathlib import Path

from polyrea.adapters.chain import decode_fills
from polyrea.adapters.http import HttpClient
from polyrea.adapters.polymarket import merge_cursor_pages

FIX = Path(__file__).parent / "fixtures"
W = "0xf0318c32136c2db7fec88b84869aee6a1106c80c"


def _row(ts, tx, size=1.0):
    return {"timestamp": ts, "transactionHash": tx, "asset": "a", "type": "TRADE", "side": "BUY", "size": size, "price": 0.5, "conditionId": "c"}


def test_merge_cursor_pages_removes_boundary_repeats_only():
    p1 = [_row(1, "a"), _row(2, "b"), _row(3, "c"), _row(3, "c")]  # two identical fills at ts 3
    p2 = [_row(3, "c"), _row(3, "c"), _row(4, "d")]  # re-read from ts 3
    merged = merge_cursor_pages([p1, p2])
    assert [r["transactionHash"] for r in merged] == ["a", "b", "c", "c", "d"]


def test_merge_cursor_pages_keeps_new_rows_at_boundary():
    p1 = [_row(1, "a"), _row(5, "b")]
    p2 = [_row(5, "b"), _row(5, "z"), _row(6, "c")]  # "z" first seen on page 2
    merged = merge_cursor_pages([p1, p2])
    assert [r["transactionHash"] for r in merged] == ["a", "b", "z", "c"]


def test_merge_cursor_pages_multi_page_same_timestamp():
    p1 = [_row(1, "a"), _row(2, "x")]
    p2 = [_row(2, "x"), _row(2, "y")]
    p3 = [_row(2, "x"), _row(2, "y"), _row(3, "q")]
    merged = merge_cursor_pages([p1, p2, p3])
    assert [r["transactionHash"] for r in merged] == ["a", "x", "y", "q"]


def test_decode_v2_receipt_maker_role():
    rec = json.loads((FIX / "receipt_v2_maker.json").read_text(encoding="utf-8"))
    fills = decode_fills(rec)
    mine = [f for f in fills if f.maker == W]
    assert len(mine) == 1
    f = mine[0]
    assert f.version == "v2" and f.side == "BUY"
    assert f.role_of(W) == "maker"
    assert f.shares == 52 and f.usdc == 26 and abs(f.price - 0.5) < 1e-12
    assert f.token_id == "34344679499028828435361410606280794811838854320630032365355848756799176559692"
    # the counterparty's own order is the taker leg
    taker_leg = [x for x in fills if x.maker == "0xac3d38db0800dfff1c1059f7867f8f5f72be2086"][0]
    assert taker_leg.role_of("0xac3d38db0800dfff1c1059f7867f8f5f72be2086") == "taker"


def test_decode_v1_receipt_maker_role():
    rec = json.loads((FIX / "receipt_v1_maker.json").read_text(encoding="utf-8"))
    fills = decode_fills(rec)
    mine = [f for f in fills if f.maker == W]
    assert len(mine) == 1
    f = mine[0]
    assert f.version == "v1" and f.side == "BUY" and f.role_of(W) == "maker"
    assert f.shares == 50000 and f.usdc == 27500


def test_http_cache_roundtrip(tmp_path, monkeypatch):
    client = HttpClient(cache_dir=tmp_path)
    client.cache.put("k", "https://x", 200, b'{"a": 1}')
    assert client.cache.get("k", None)[1] == b'{"a": 1}'
    assert client.cache.get("k", -1) is None  # expired
    assert HttpClient.build_url("https://h/p", {"a": 1, "b": None}) == "https://h/p?a=1"


def test_error_bodies_are_never_served_from_cache(tmp_path):
    import hashlib

    client = HttpClient(cache_dir=tmp_path, offline=True)
    url = "https://api.kraken.com/0/public/Trades?pair=XBTUSD"
    key = hashlib.sha256(f"GET {url} ".encode()).hexdigest()
    client.cache.put(key, url, 200, b'{"error": ["EGeneral:Too many requests"]}')
    ok = lambda d: not d.get("error")  # noqa: E731
    import pytest

    with pytest.raises(Exception):  # offline + rejected cache -> must not return the error body
        client.get_json("https://api.kraken.com/0/public/Trades", {"pair": "XBTUSD"}, adapter="k", max_age=None, cache_if=ok)
    data, _ = client.get_json("https://api.kraken.com/0/public/Trades", {"pair": "XBTUSD"}, adapter="k", max_age=None)
    assert data["error"]  # without a validator the raw cached body is returned


class _FakeTradesApi:
    """data-api /trades stand-in: newest first, default page 100 when ``limit`` is absent."""

    def __init__(self, rows):
        self.rows = sorted(rows, key=lambda r: -r["timestamp"])

    def get_json(self, url, params, adapter, max_age=None, **_):
        from polyrea.evidence import Source

        p = dict(params)
        sel = [r for r in self.rows if (p.get("start") is None or r["timestamp"] >= p["start"]) and r["timestamp"] <= p["end"]]
        off, lim = int(p.get("offset", 0)), int(p.get("limit", 100))
        return sel[off : off + lim], Source(adapter=adapter, url=url, fetched_at="t")


def test_descending_scan_keeps_every_row_of_a_dense_second():
    from polyrea.adapters.polymarket import PolymarketData

    rows = [_row(1000 + i // 3, f"a{i}") for i in range(600)]  # 3 per second
    rows += [_row(1250, f"dense{i}") for i in range(1203)]  # one second with > 2 full pages
    rows += [_row(1300 + i, f"b{i}") for i in range(400)]
    pm = PolymarketData(http=_FakeTradesApi(rows))
    got, _, cov = pm.market_trades("c", start=0, end=2000, taker_only=False)
    assert len(got) == len(rows)
    assert sum(r["transactionHash"].startswith("dense") for r in got) == 1203
    assert [r["timestamp"] for r in got] == sorted(r["timestamp"] for r in got)
    assert cov.status == "complete"


def test_offset_walk_reports_truncation_at_the_offset_cap():
    from polyrea.adapters.polymarket import PolymarketData

    rows = [_row(1250, f"d{i}") for i in range(6000)]  # more than the API's offset cap allows
    pm = PolymarketData(http=_FakeTradesApi(rows))
    _, _, cov = pm.market_trades("c", start=0, end=2000, taker_only=False)
    assert cov.status == "partial"

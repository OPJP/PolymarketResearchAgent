import pytest

from polyrea.pit import (
    ExternalRegistry,
    ExternalSourceSpec,
    LookAheadError,
    PITStore,
    Print,
    TimeSeries,
    audit_no_lookahead,
)


def _store():
    s = PITStore()
    # minute candles keyed by open time; close known 60 s later
    s.add_series(TimeSeries.build("spot", [(0, 100.0), (60, 101.0), (120, 99.0), (180, 105.0)], availability_lag=60))
    s.add_tape("tok", [Print(10, "tok", "BUY", 0.40, 5), Print(70, "tok", "BUY", 0.45, 5), Print(200, "tok", "SELL", 0.9, 5)])
    s.add_market(
        {"conditionId": "c1", "question": "Q?", "endDate": "2026-01-01", "outcomePrices": '["1","0"]', "closed": True, "volume": 1e6},
        listed_at=0,
        resolution=(300, {"tok": 1.0}),
    )
    s.add_market({"conditionId": "c2", "question": "later"}, listed_at=500)
    return s


def test_latest_respects_availability_lag():
    v = _store().view(119)
    assert v.latest("spot") == (0, 100.0)  # the 60-open candle closes at 120, not visible yet
    v = _store().view(120)
    assert v.latest("spot") == (60, 101.0)


def test_explicit_future_request_raises():
    v = _store().view(100)
    with pytest.raises(LookAheadError):
        v.latest("spot", at=101)


def test_history_window_and_readonly():
    ev, vals = _store().view(239).history("spot", lookback=1000)
    assert list(ev) == [0, 60, 120]  # candle opened at 180 closes at 240
    ev, vals = _store().view(240).history("spot", lookback=1000)
    assert list(ev) == [0, 60, 120, 180]
    with pytest.raises(ValueError):
        vals[0] = 1.0


def test_tape_is_cut_at_t():
    v = _store().view(100)
    assert [p.ts for p in v.prints("tok", 1000)] == [10, 70]
    assert v.last_price("tok") == 0.45


def test_market_post_hoc_fields_masked_and_unlisted_hidden():
    v = _store().view(100)
    m = v.market("c1")
    assert m["question"] == "Q?"
    for forbidden in ("outcomePrices", "closed", "volume"):
        assert forbidden not in m
    assert v.market("c2") is None
    assert v.listed_markets() == ["c1"]


def test_resolution_only_after_resolution_time():
    assert _store().view(299).resolution("c1") is None
    assert _store().view(300).resolution("c1") == {"tok": 1.0}


def test_audit_passes_for_honest_strategy():
    store = _store()

    def honest(view, _):
        p = view.last_price("tok")
        spot = view.latest("spot")
        return {"buy": p is not None and p < 0.5 and spot is not None and spot[1] >= 100}

    report = audit_no_lookahead(honest, store, [(t, None) for t in (5, 50, 100, 130, 250)])
    assert report["passed"], report


def test_audit_catches_closure_leak():
    store = _store()
    future_close = store.series["spot"].values[-1]  # captured from the full store

    def leaky(view, _):
        return {"buy": future_close > 104}

    def leaky_via_store(view, _):
        # reaches around the view into the backing store's last value
        s = view._store.series["spot"]
        return {"buy": bool(s.values[-1] > 104)} if len(s) else {"buy": False}

    # a strategy that reaches around the view into the backing store is caught
    report = audit_no_lookahead(leaky_via_store, store, [(t, None) for t in (100, 130)])
    assert not report["passed"]
    assert report["mismatch_count"] == 2
    # A constant captured from the future before the run cannot be detected by
    # re-running the same code; that class of leak (fitted parameters) is
    # prevented structurally by walk-forward fitting, see test_backtest.py.
    assert audit_no_lookahead(leaky, store, [(100, None)])["passed"]


def test_truncated_store_has_no_future():
    t = _store().truncated(100)
    assert len(t.series["spot"]) == 1  # only the candle available at 60
    assert [p.ts for p in t.tapes["tok"]] == [10, 70]
    assert "c2" not in t.markets
    assert "outcomePrices" not in t.markets["c1"]
    assert t.resolution == {}


def test_external_spec_validation(tmp_path):
    with pytest.raises(ValueError):
        ExternalSourceSpec("x", "http://insecure", "", 0, 1)
    with pytest.raises(ValueError):
        ExternalSourceSpec("x", "https://ok", "", 0, 1, availability_lag_seconds=-1)
    reg = ExternalRegistry(tmp_path / "ext.json")
    reg.register(ExternalSourceSpec("my.series", "https://example.org/{start}", "data", "t", "v", description="d"))
    reg2 = ExternalRegistry(tmp_path / "ext.json")
    assert "my.series" in reg2.sources and "coinbase.btcusd.1m" in reg2.sources


def test_external_fetch_parses_and_lags(tmp_path):
    class FakeHttp:
        def get_json(self, url, params, adapter, max_age):
            from polyrea.evidence import Source

            return {"data": [{"t": "1000", "v": "1.5"}, {"t": "1060", "v": "2.5"}, {"bad": 1}]}, Source(adapter, url, "now")

    reg = ExternalRegistry(None)
    reg.register(ExternalSourceSpec("s", "https://x/{start}/{end}", "data", "t", "v", availability_lag_seconds=30, chunk_seconds=10_000))
    ts, sources = reg.fetch("s", 900, 2000, http=FakeHttp())
    assert list(ts.event_ts) == [1000, 1060]
    assert list(ts.available_ts) == [1030, 1090]
    assert len(sources) == 1

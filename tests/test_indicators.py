"""Indicators and hidden-dimension tests used by the deep reverse engineering (research/reverse_engineering/tools/indicators.py)."""
import importlib.util
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("indicators", ROOT / "research" / "reverse_engineering" / "tools" / "indicators.py")
ind = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ind)

UNITS = np.array([(i * 300.0, i * 300.0 + 300.0) for i in range(120)])


def _planted(rng, lag_s, share=0.4, n_ev=500, n_noise=800):
    ev = np.sort(rng.uniform(0, UNITS[-1, 1], n_ev))
    keep = rng.random(n_ev) < share
    dec = np.r_[ev[keep] + lag_s + rng.normal(0, 0.05, keep.sum()), rng.uniform(0, UNITS[-1, 1], n_noise)]
    return ev, dec, keep


def test_event_study_finds_planted_lag_and_side():
    rng = np.random.default_rng(3)
    ev, dec, keep = _planted(rng, 0.75)
    es = rng.choice([-1.0, 1.0], len(ev))
    ds = np.r_[es[keep], rng.choice([-1.0, 1.0], len(dec) - keep.sum())]
    r = ind.event_study(dec, ev, UNITS, max_lag_s=5, bin_s=0.25, n_null=200, decision_sign=ds, event_sign=es)
    assert abs(r["shape_peak_lag_s"] - 0.75) <= 0.25
    assert r["p_link"] < 0.01 and r["shape_lift"] > 5
    assert r["signed"]["p_link"] < 0.01 and r["signed"]["shape_z"] > 0


def test_event_study_sees_a_wallet_that_leads_the_feed():
    rng = np.random.default_rng(4)
    ev, dec, _ = _planted(rng, -1.0)
    r = ind.event_study(dec, ev, UNITS, max_lag_s=5, bin_s=0.25, n_null=200)
    assert abs(r["shape_peak_lag_s"] + 1.0) <= 0.25 and r["p_link"] < 0.01


def test_swap_null_ignores_shared_time_in_window_structure():
    rng = np.random.default_rng(5)
    def at_open(n):
        return UNITS[rng.integers(0, len(UNITS), n), 0] + np.minimum(rng.exponential(15, n), 299)
    r = ind.event_study(at_open(1200), at_open(600), UNITS, max_lag_s=5, bin_s=0.25, n_null=200)
    assert r["p_link"] > 0.01


def _inside(rng, units, rate, level):
    return np.concatenate([rng.uniform(a, b, rng.poisson(rate * v)) for (a, b), v in zip(units, level)])


def test_shared_activity_level_is_not_a_link():
    # Volatile windows have more jumps and more bot activity, independently placed: no timing link.
    rng = np.random.default_rng(9)
    units = np.array([(i * 300.0, i * 300.0 + 300.0) for i in range(300)])
    vol = rng.lognormal(0, 0.9, len(units))
    r = ind.event_study(_inside(rng, units, 6, vol), _inside(rng, units, 3, vol), units, max_lag_s=10, bin_s=0.5,
                        n_null=200)
    assert r["median_lift"] > 1.2 or r["p_level"] > 0.01  # the level alone may be lifted...
    assert r["p_link"] > 0.01  # ...but no localized timing peak is credited


def test_shared_trend_is_not_a_side_link():
    rng = np.random.default_rng(10)
    units = np.array([(i * 300.0, i * 300.0 + 300.0) for i in range(600)])
    pu = rng.uniform(0.1, 0.9, len(units))
    dec, ev = _inside(rng, units, 5, np.ones(len(units))), _inside(rng, units, 3, np.ones(len(units)))
    u_of = lambda ts: np.searchsorted(units[:, 0], ts, side="right") - 1
    side = lambda ts: np.where(rng.random(len(ts)) < pu[u_of(ts)], 1.0, -1.0)
    r = ind.event_study(dec, ev, units, max_lag_s=10, bin_s=0.5, n_null=200, decision_sign=side(dec),
                        event_sign=side(ev))
    assert r["signed"]["p_link"] > 0.01


def test_games_of_unequal_length_still_find_the_link():
    rng = np.random.default_rng(11)
    length = rng.uniform(1500, 2500, 80)
    starts = np.r_[0.0, np.cumsum(length + 100)[:-1]]
    games = np.c_[starts, starts + length]
    ev = np.concatenate([rng.uniform(a, b - 10, 30) for a, b in games])
    hit = rng.random(len(ev)) < 0.5
    dec = np.r_[ev[hit] + 2.0, np.concatenate([rng.uniform(a, b, 20) for a, b in games])]
    for null in ("auto", "jitter"):  # auto swaps within length classes
        r = ind.event_study(dec, ev, games, max_lag_s=10, bin_s=0.5, n_null=200, null=null)
        assert r["units_in_null"] >= 0.8 * len(games)
        assert abs(r["shape_peak_lag_s"] - 2.0) <= 0.5 and r["p_link"] < 0.01
    indep = np.concatenate([rng.uniform(a, b, 35) for a, b in games])
    assert ind.event_study(indep, ev, games, max_lag_s=10, bin_s=0.5, n_null=200, null="jitter")["p_link"] > 0.01


def test_event_study_keeps_lags_inside_units_and_rejects_overlap():
    r = ind.event_study([10.5], [10.0], [(0, 10.2), (10.2, 20.4)], max_lag_s=2, bin_s=0.5, n_null=20)
    assert sum(r["obs"]) == 0  # the decision is in the next unit
    try:
        ind.event_study([1.0], [1.0], [(0, 10), (5, 15)], n_null=5)
        raise AssertionError("overlap accepted")
    except ValueError:
        pass


def test_detectors_do_not_look_ahead():
    rng = np.random.default_rng(6)
    t = ind.grid(0, 600, 0.1)
    x = np.cumsum(rng.normal(0, 1, len(t)))
    y = x.copy()
    y[3000:] += 40.0
    for f in (lambda v: ind.jumps(t, v, 5, k=3), lambda v: ind.cusum(t, v), lambda v: ind.crossings(t, v, 0.0),
              lambda v: ind.divergence(t, v, x * 0.5, 5, k=3)):
        a, b = f(x)[0], f(y)[0]
        assert np.array_equal(a[a < t[3000]], b[b < t[3000]])
    z = ind.zscore(x, 50)
    z2 = ind.zscore(y, 50)
    assert np.allclose(z[:3000], z2[:3000], equal_nan=True)


def test_asof_and_counts():
    t = ind.grid(0, 5, 1.0)
    assert np.allclose(ind.asof(t, [0.5, 2.0], [7, 9]), [np.nan, 7, 9, 9, 9], equal_nan=True)
    assert ind.counts(t, [0.1, 0.2, 3.9, 4.0]).tolist() == [0, 2, 0, 0, 2]  # (t_k-1, t_k]: known at t_k
    assert ind.counts(t, [3.9, 0.1], weights=[5.0, 2.0]).tolist() == [0, 2, 0, 0, 5]


def test_multiple_testing_helpers():
    p = np.array([0.001, 0.02, 0.03, 0.5])
    q = ind.bh(p)
    assert np.all(q >= p) and q[0] == 0.004 and np.isclose(q[2], 0.04)
    assert np.allclose(ind.holm(p), [0.004, 0.06, 0.06, 0.5])
    q = ind.bh([0.001, np.nan, 0.03])
    assert np.isnan(q[1]) and np.allclose(q[[0, 2]], [0.002, 0.03])


def test_screen_can_pass_a_true_indicator_in_a_large_family():
    # A permutation p is floored at 1/(n_null+1); the Gumbel tail keeps BH usable for many indicators.
    rng = np.random.default_rng(12)
    ev, dec, _ = _planted(rng, 0.5)
    family = {"true": (ev, None)}
    family.update({f"noise{i}": (np.sort(rng.uniform(0, UNITS[-1, 1], 500)), None) for i in range(59)})
    rows = ind.screen(dec, family, UNITS, max_lag_s=5, bin_s=0.5, n_null=100)
    best = rows[0]
    assert best["name"] == "true" and best["q_bh"] < 0.05
    assert sum(r["q_bh"] < 0.05 for r in rows) <= 3


def test_incremental_auc_credits_only_new_information():
    rng = np.random.default_rng(7)
    y = (rng.random(3000) < 0.25).astype(int)
    base = rng.normal(0, 1, 3000) + y
    g = np.repeat(np.arange(30), 100)
    useful = ind.incremental_auc(y, base, rng.normal(0, 1, 3000) + 0.8 * y, g, n_boot=200)
    redundant = ind.incremental_auc(y, base, base + rng.normal(0, 0.01, 3000), g, n_boot=200)
    assert useful["gain"] > 0.03 and useful["p_gain_le_0"] < 0.01
    assert abs(redundant["gain"]) < 0.01 and redundant["p_gain_le_0"] > 0.01
    assert abs(ind.weighted_auc([0, 1, 0, 1], [0.1, 0.9, 0.5, 0.5]) - 0.875) < 1e-12


def test_residual_clustering_flags_a_common_driver():
    rng = np.random.default_rng(8)
    shared = rng.uniform(0, 20000, 50)
    ts = np.r_[np.repeat(shared, 3) + rng.normal(0, 0.3, 150), rng.uniform(0, 20000, 500)]
    mk = np.r_[np.tile([0, 1, 2], 50), rng.integers(0, 6, 500)]
    hit = ind.residual_clustering(ts, mk, n_null=150)
    assert hit["p"] < 0.01 and hit["ratio"] > 2 and hit["top_clusters"][0][1] >= 3
    none = ind.residual_clustering(rng.uniform(0, 20000, 650), rng.integers(0, 6, 650), n_null=150)
    assert none["p"] > 0.01


def test_residual_clustering_ignores_shared_schedules_and_minute_scale_coactivity():
    rng = np.random.default_rng(13)
    opens = np.arange(0, 40 * 300, 300.0)
    tracks = [np.concatenate([w + rng.exponential(4, rng.poisson(1)) for w in opens]) for _ in range(3)]
    ts, mk = np.concatenate(tracks), np.repeat([0, 1, 2], [len(v) for v in tracks])
    assert ind.residual_clustering(ts, mk, n_null=150, period_s=300.0)["p"] > 0.01
    periods = np.sort(rng.uniform(0, 200000, 300))
    tracks = [np.concatenate([p + rng.uniform(0, 600, rng.poisson(1.5)) for p in periods]) for _ in range(6)]
    ts, mk = np.concatenate(tracks), np.repeat(np.arange(6), [len(v) for v in tracks])
    assert ind.residual_clustering(ts, mk, n_null=150)["p"] > 0.01
    try:
        ind.residual_clustering([], [])
        raise AssertionError("empty input accepted")
    except ValueError:
        pass
    assert np.isnan(ind.residual_clustering([1.0, 500.0], ["a", "a"], n_null=10)["ratio"])


def test_specific_event_helpers_are_causal():
    t = ind.grid(0, 10, 1.0)
    assert ind.first_occurrence(t, t % 4 == 3, [0, 5]).tolist() == [3.0, 7.0]
    ev, sg = ind.gate([1.5, 3.5, 6.5], [1, -1, 1], t, t, lo=3, hi=5.5)  # state read as of the event: 1, 3, 6
    assert ev.tolist() == [3.5] and sg.tolist() == [-1]
    a, s = ind.compound([1.0, 5.0], [1, -1], [1.5, 9.0], within_s=1.0, absent=True)
    assert a.tolist() == [6.0] and s.tolist() == [-1]  # fires once the absence is known
    b, _ = ind.compound([1.0, 5.0], None, [1.5, 9.0], within_s=1.0, absent=False)
    assert b.tolist() == [1.5]
    f = ind.event_features([0.5, 2.0, 2.5], [1.0, 2.0], [1, -1], horizons=(1.0,))
    assert f["since_last"].tolist() == [np.inf, 0.0, 0.5] and f["last_sign"].tolist() == [0, -1, -1]
    assert f["count_1s"].tolist() == [0, 1, 1]


def _profiled(rng, units, rate, level, scale):
    return np.concatenate([a + np.minimum(rng.exponential(scale, rng.poisson(rate * v)), b - a - 1e-6)
                           for (a, b), v in zip(units, level)])


def test_activity_level_times_open_profile_is_not_a_link():
    # The realistic crypto case: volatile windows carry more of both, and both bunch after the open.
    rng = np.random.default_rng(14)
    units = np.array([(i * 300.0, i * 300.0 + 300.0) for i in range(200)])
    vol = rng.lognormal(0, 1, len(units))
    r = ind.event_study(_profiled(rng, units, 8, vol, 40), _profiled(rng, units, 3, vol, 40), units, max_lag_s=60,
                        bin_s=1, n_null=200)
    assert r["p_link"] > 0.01


def test_games_profiled_from_their_start_are_not_a_link():
    rng = np.random.default_rng(15)
    length = rng.uniform(1500, 3000, 60)
    starts = np.r_[0.0, np.cumsum(length + 100)[:-1]]
    games = np.c_[starts, starts + length]
    vol = rng.lognormal(0, 0.7, 60)
    r = ind.event_study(_profiled(rng, games, 30, vol, 60), _profiled(rng, games, 15, vol, 60), games, max_lag_s=10,
                        bin_s=0.5, n_null=200)
    assert r["null"] == "swap" and r["p_link"] > 0.01


def test_broad_response_is_found():
    rng = np.random.default_rng(16)
    ev = rng.uniform(0, UNITS[-1, 1], 800)
    k = rng.random(800) < 0.3
    dec = np.r_[ev[k] + rng.uniform(0, 12, k.sum()), rng.uniform(0, UNITS[-1, 1], 1000)]
    r = ind.event_study(dec, ev, UNITS, max_lag_s=30, bin_s=1, n_null=200)
    assert r["p_link"] < 0.01 and 0 <= r["shape_peak_lag_s"] <= 12 and r["shape_width_s"] >= 4


def test_period_null_has_no_edge_bias_on_short_spans():
    rng = np.random.default_rng(17)
    ts = np.concatenate([rng.uniform(0, 7200, 300) for _ in range(4)])
    r = ind.residual_clustering(ts, np.repeat(np.arange(4), 300), n_null=200, period_s=300.0)
    assert r["p"] > 0.01 and 0.8 < r["ratio"] < 1.25


def test_ledger_row_keeps_legacy_results_whole():
    row = ind.ledger_row("binance_lead", "spot", "queue imbalance", "250 ms", {"lead_ms": 250, "p": 0.001},
                         "legacy", "drives")
    assert row["result"] == {"lead_ms": 250, "p": 0.001}
    row = ind.ledger_row("x", "spot", "d", "e", {"p_link": 0.2, "other": 1}, "BUILD", "no_effect")
    assert row["result"] == {"p_link": 0.2}

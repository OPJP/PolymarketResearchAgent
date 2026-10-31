"""One-off: turn code/final_rule.py (R2, archived as code/final_rule_r2.py) into rule R3 (iteration 4)."""
from pathlib import Path

p = Path(__file__).resolve().parents[1] / "code" / "final_rule.py"
s = p.read_text()

new_doc = '''"""Frozen rule for the directional-maker cluster (bosona, almach, mo-money), BTC 5m Up/Down. Iteration 4 rule R3.

R3 = R2 (iteration 2; archived unchanged in final_rule_r2.py) with two changes, both chosen on the iteration-4
VALIDATE (2026-10-27..30, the second half of the released lot):
* the presence models are refitted on the expanded BUILD (2026-10-09..26: old BUILD + old VALIDATE + the lot's first
  half) with the same LightGBM parameters (code4/train6.py, code4/train4.py);
* the operator's clock schedule is an input: UTC hour, weekday and the US-session flag (weekday 12:00-21:00 UTC), the
  boundary at which the cluster's order size switches (iteration-4 calldata finding).
Everything else (tape hygiene, features, side, price, selection models and thresholds) is R2's.

* Tape hygiene: every data-api taker print in a transaction where a cluster wallet traded (maker or taker) is removed
  before any feature is computed.
* Presence: P(cluster gets >= 1 maker BUY fill on side s in the 10-s bin [t, t+10)), t in [0, 300) s
  = presence3_rule.txt on features published by t (features2.build_panel + clock): time, side, clean-tape activity,
  Binance 1-s fair value of the TWAP-60 settlement, z, returns, realized vol, edge = fair - last clean print, window
  path features, previous-window proxy outcome and strike move, UTC hour, weekday, US-session flag. No own-state.
  Baseline: presence3_activity.txt (market activity only, same BUILD). Own-inventory variant: presence3_own.txt.
* Side (bins where it fills exactly one side): the side with the higher predicted presence.
* Price: last clean taker print on s strictly before the fill second, minus 0.01, rounded to 0.01.
* Selection: R2's selection2_all.txt / THETA_SEL (unchanged).
* Per-window rule PnL: sum over bins and sides of P(fill) * (payout_s - rule price).

evaluate(start_ts, end_ts, intervals=None) loads [start_ts, end_ts) through the polyrea adapters (Gamma windows,
data-api taker tapes [start-120, end) and the three wallets' activity, Binance 1-s archive), applies the frozen
models and returns presence / side / price / PnL / selection metrics with the market-activity-only baselines, pooled
and per wallet. With intervals (list of [a, b) pairs) only windows starting in them count. Nothing is fitted here.
local=True (development only) reads cached day files when they exist. The rule reads no live recording;
ALLOW_SEALED is kept for the examiner's driver.
"""
'''
i = s.index("from __future__ import annotations")
s = new_doc + s[i:]


def rep(old, new):
    global s
    assert s.count(old) == 1, old[:80]
    s = s.replace(old, new)


rep('''MODEL = "all_path_xwin"          # chosen on VALIDATE (iteration 2)
BASELINE = "activity"            # market-activity-only (co-occurrence) baseline
OWN_MODEL = "all_path_xwin+own"  # reported separately (own inventory)''',
    '''ALLOW_SEALED = False             # only the examiner's driver sets True (no live input is read by R3)
MODEL = "rule"                   # presence3_rule.txt: R2 features + clock, refit on BUILD 2026-10-09..26 (iteration 4)
BASELINE = "activity"            # presence3_activity.txt: market-activity-only (co-occurrence) baseline, same BUILD
OWN_MODEL = "own"                # presence3_own.txt: reported separately (own inventory)
CLOCK = ["hour_utc", "dow", "us_session"]
FEATS = {"rule": SETS["all_path_xwin"] + CLOCK, "activity": SETS["activity"],
         "own": SETS["all_path_xwin"] + CLOCK + ["inv_s", "inv_o"]}''')

rep('''def evaluate(start_ts: int, end_ts: int, local: bool = False, n_perm: int = 99, cache_only: bool = False) -> dict:''',
    '''def _add_clock(panel: pd.DataFrame) -> pd.DataFrame:
    t = pd.to_datetime(panel["start_ts"], unit="s")
    panel["hour_utc"] = (t.dt.hour + t.dt.minute / 60).astype(np.float32).to_numpy()
    panel["dow"] = t.dt.day_of_week.astype(np.int8).to_numpy()
    panel["us_session"] = ((panel["dow"] < 5) & (panel["hour_utc"] >= 12) & (panel["hour_utc"] < 21)).astype(np.int8)
    return panel


def _wallet_labels(panel: pd.DataFrame, w: pd.DataFrame, mk: pd.DataFrame, wallet: str) -> np.ndarray:
    """y for one wallet: >= 1 maker BUY fill of that wallet on the bin's side in [t, t+10)."""
    side_of = {**{t: (c, 1, s) for t, c, s in zip(w["up_token"], w["cid"], w["start_ts"])},
               **{t: (c, 0, s) for t, c, s in zip(w["down_token"], w["cid"], w["start_ts"])}}
    m = mk[mk["wallet"] == wallet]
    keys = set()
    for tok, ts in zip(m["token_id"], m["ts"]):
        v = side_of.get(tok)
        if v is None:
            continue
        rel = int((ts - v[2]) // 10 * 10)
        if 0 <= rel < 300:
            keys.add((v[0], v[1], rel))
    return np.array([(c, sd, r) in keys for c, sd, r in zip(panel["cid"], panel["side_up"], panel["rel"])], dtype=np.int8)


def evaluate(start_ts: int, end_ts: int, intervals=None, local: bool = False, n_perm: int = 99,
             cache_only: bool = False) -> dict:''')

rep('''    w = _windows(start_ts, end_ts)
    tk = _tapes(w, pm, end_ts, local)''', '''    w = _windows(start_ts, end_ts)
    if intervals:
        keep = np.zeros(len(w), dtype=bool)
        for a_, b_ in intervals:
            keep |= (w["start_ts"].to_numpy() >= a_) & (w["start_ts"].to_numpy() < b_)
        w = w[keep].reset_index(drop=True)
    tk = _tapes(w, pm, end_ts, local)''')

rep('''    for nm in (MODEL, BASELINE, OWN_MODEL):
        m = lgb.Booster(model_file=str(HERE / f"presence2_{nm}.txt"))
        panel["p_" + nm] = m.predict(panel[SETS[nm]])''', '''    panel = _add_clock(panel)
    for nm in (MODEL, BASELINE, OWN_MODEL):
        m = lgb.Booster(model_file=str(HERE / f"presence3_{nm}.txt"))
        panel["p_" + nm] = m.predict(panel[FEATS[nm]])''')

rep('''    # price: last clean print on s strictly before the fill second - 0.01''', '''    per_wallet = {}
    for addr, name in CLUSTER.items():
        yw = _wallet_labels(panel, w, mk, addr)
        pw = panel.assign(y=yw)
        per_wallet[name] = {"fills": int((mk["wallet"] == addr).sum()),
                            "presence_auc": _auc(yw, panel["p_" + MODEL].to_numpy()),
                            "presence_auc_activity_baseline": _auc(yw, panel["p_" + BASELINE].to_numpy()),
                            "side": side_metrics(pw, "p_" + MODEL)["acc"] if yw.sum() else float("nan")}
    # price: last clean print on s strictly before the fill second - 0.01''')

rep('''    pred, actual = [], []
    for r in mk.itertuples(index=False):''', '''    pred, actual, pw_wal = [], [], []
    for r in mk.itertuples(index=False):''')

rep('''        pred.append(round(ls - PRICE_OFFSET, 2))
        actual.append(r.price)''', '''        pred.append(round(ls - PRICE_OFFSET, 2))
        actual.append(r.price)
        pw_wal.append(r.wallet)''')

rep('''                    "within_0.01": float(np.mean(e <= 0.0105)) if len(e) else float("nan")}''',
    '''                    "within_0.01": float(np.mean(e <= 0.0105)) if len(e) else float("nan")}
    pw_wal = np.asarray(pw_wal)
    for addr, name in CLUSTER.items():
        k = pw_wal == addr
        per_wallet[name]["price_within_0.01"] = float(np.mean(e[k] <= 0.0105)) if k.any() else float("nan")''')

rep('''    usd = float((mk2["price"] * mk2["shares"]).sum())''', '''    usd = float((mk2["price"] * mk2["shares"]).sum())
    rule_w = pr.groupby("cid")["rule_pnl"].sum()
    for addr, name in CLUSTER.items():
        m2 = mk2[mk2["wallet"] == addr]
        ww = ((m2["won"] - m2["price"]) * m2["shares"]).groupby(m2["c"]).sum()
        jj = pd.concat([ww.rename("wallet"), rule_w.rename("rule")], axis=1).dropna()
        per_wallet[name]["pnl_pearson"] = float(jj.corr().iloc[0, 1]) if len(jj) > 2 else float("nan")
        per_wallet[name]["pnl_spearman"] = float(jj.corr(method="spearman").iloc[0, 1]) if len(jj) > 2 else float("nan")
        per_wallet[name]["pnl_windows"] = int(len(jj))
    res["per_wallet"] = per_wallet''')

p.write_text(s)
print("patched", s.count("presence3_"), s.count("per_wallet"))

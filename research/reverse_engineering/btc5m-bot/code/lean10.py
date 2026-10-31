"""Iteration 10 (panel iter9 assumptions P1 = X82): the per-window PnL as the LARGE-ORDER LEAN, and a PnL test-retest ceiling
with the own-state SIZE FEEDBACK re-simulated (the iteration-9 ceiling 1 - (1 - q) kappa held sizes fixed).
Data: on-chain cluster fills (fills.parquet), orders = order hashes; VALIDATE 10-16..22 (outcomes settle PnL only), BUILD
10-09..15 for the size tables. Large = an order's filled shares > 1.5 x the day's modal order size.
Step 1 (decomposition, per wallet and pooled): corr(window PnL, large-only PnL), corr(window PnL, small-only PnL), the variance
shares, corr(window PnL, netLarge x (2Y - 1)), sign(netLarge) vs the outcome, P(large) by the operator's net state.
Step 2 (replays): every observed order is a decision at its time, side and price; in a replay it fills with probability q
(independently across replays), with its observed fill fraction f; its size class is
  V0 fixed: the observed class (the iteration-9 assumption, simulated as a check of the formula);
  V1 state-consistent: the observed class when the replay's operator-net state on o (flat |net| < 30 / long / short, the
     three wallets' net shares toward o before the order, in the replay's own fills) equals the observed state; else drawn
     from the BUILD table P(large | state, wallet);
  V2 full re-draw: always drawn from P(large | replay state, wallet) (the panel's lower bound: the fitted size rule is noisier
     than the bot's).
Report r(replay, replay) over pairs and r(replay, wallet), Pearson and Spearman, pooled and per wallet, at q = 0.61 / 0.70.
  V3 coupled monotone: one uniform u per decision shared by all replays and drawn consistent with the observed size in the
     observed state (u < P(large | observed state) iff large); in a replay, large iff u < P(large | replay state, wallet): the
     most deterministic size rule consistent with the state table (an upper bound among the feedback variants).
Usage: python lean10.py OUT_JSON [variants]"""
import os, sys, json
import numpy as np, pandas as pd
from scipy.stats import spearmanr

C = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "..", ".cache", "re", "btc5m-bot"))
VAL = (1792108800, 1792713600); BUILD = (1791504000, 1792108800)
R = 200
VARIANTS = ((0, "V0_fixed"), (1, "V1_state_consistent"), (2, "V2_full_redraw"), (3, "V3_coupled_monotone"))


def orders():
    f = pd.read_parquet(C + "/fills.parquet", columns=["ts", "block", "li", "oh", "wallet", "role", "shares", "price", "fee_usd", "start_ts", "is_up", "up_payout", "rel"])
    f = f.sort_values(["block", "li"])
    f["day"] = pd.to_datetime(f.start_ts, unit="s").dt.strftime("%m-%d")
    won = np.where(f.is_up, f.up_payout, 1 - f.up_payout)
    f["x"] = f.shares * (won - f.price) - f.fee_usd + 0.5 * f.fee_usd * (f.role == "T")
    f["cost"] = f.shares * f.price + f.fee_usd - 0.5 * f.fee_usd * (f.role == "T")
    o = f.groupby("oh", sort=False).agg(wallet=("wallet", "first"), w=("start_ts", "first"), day=("day", "first"), ts=("ts", "first"),
                                        block=("block", "first"), li=("li", "first"), up=("is_up", "first"), pay=("up_payout", "first"),
                                        sh=("shares", "sum"), cost=("cost", "sum"), x=("x", "sum"), first=("role", "first"), rel=("rel", "first")).reset_index()
    mode = o.groupby("day").sh.agg(lambda v: v.round().value_counts().idxmax())
    o["mode"] = o.day.map(mode)
    o["large"] = o.sh > 1.5 * o["mode"]
    o["nominal"] = np.where(o.large, np.maximum(100.0, o.sh.round()), o["mode"])
    o["frac"] = np.clip(o.sh / o.nominal, 0, 1)
    o["won"] = np.where(o.up, o.pay, 1 - o.pay)
    o["cps"] = o.cost / o.sh  # cost per share incl. net fee
    o["sgn"] = np.where(o.up, 1.0, -1.0)
    return o.sort_values(["block", "li"]).reset_index(drop=True), {k: float(v) for k, v in mode.items()}


def state_class(net_o):
    return np.where(net_o >= 30, 2, np.where(net_o <= -30, 0, 1))  # 0 short o, 1 flat, 2 long o


def observed_states(o):
    st = np.empty(len(o), int); net = {}
    for i, (w, s, sh) in enumerate(zip(o.w.to_numpy(), o.sgn.to_numpy(), o.sh.to_numpy())):
        n = net.get(w, 0.0)
        st[i] = 2 if n * s >= 30 else (0 if n * s <= -30 else 1)
        net[w] = n + sh * s
    return st


def decomposition(o, by=None):
    g = o if by is None else o[o.wallet == by]
    g = g.assign(xl=np.where(g.large, g.x, 0.0), xs=np.where(g.large, 0.0, g.x), nl=np.where(g.large, g.sh * g.sgn, 0.0))
    per = g.groupby("w").agg(pnl=("x", "sum"), large=("xl", "sum"), small=("xs", "sum"), netL=("nl", "sum"), y=("pay", "first"))
    yy = 2 * per.y - 1
    nz = per.netL != 0
    return {"windows": int(len(per)), "corr_pnl_large": round(float(np.corrcoef(per.pnl, per.large)[0, 1]), 4),
            "corr_pnl_small": round(float(np.corrcoef(per.pnl, per.small)[0, 1]), 4),
            "var_large_over_total": round(float(per.large.var() / per.pnl.var()), 3), "var_small_over_total": round(float(per.small.var() / per.pnl.var()), 3),
            "corr_pnl_netL_x_outcome": round(float(np.corrcoef(per.pnl, per.netL * yy)[0, 1]), 4),
            "sign_netL_agrees_outcome": round(float((np.sign(per.netL[nz]) == np.sign(yy[nz])).mean()), 4), "windows_with_large": int(nz.sum()),
            "large_order_share": round(float(g.large.mean()), 4)}


def coupled_u(o, tab, obs_state, rng):
    """V3: one uniform per decision, shared by every replay, consistent with the observed size in the observed state."""
    wal = o.wallet.map({"DS": 0, "GF": 1, "XM": 2}).to_numpy(); lg = o.large.to_numpy()
    p_obs = np.array([tab[w][c] for w, c in zip(wal, obs_state)])
    r = rng.random(len(o))
    return np.where(lg, r * p_obs, p_obs + r * (1 - p_obs))


def replay(o, tab, q, variant, rng, obs_state, ucoup=None):
    n = len(o); Rr = R
    w = o.w.to_numpy(); s = o.sgn.to_numpy(); frac = o.frac.to_numpy(); mode = o["mode"].to_numpy(); won = o.won.to_numpy(); cps = o.cps.to_numpy()
    lg = o.large.to_numpy(); wal = o.wallet.map({"DS": 0, "GF": 1, "XM": 2}).to_numpy()
    big = np.where(lg, o.nominal.to_numpy(), 100.0)
    uw, inv = np.unique(w, return_inverse=True)
    pnl = np.zeros((Rr, len(uw))); pnl_w = np.zeros((3, Rr, len(uw)))
    net = np.zeros(Rr); cur = -1
    for i in range(n):
        if inv[i] != cur:
            net[:] = 0.0; cur = inv[i]
        fill = rng.random(Rr) < q
        if variant == 0:
            L_ = np.full(Rr, lg[i])
        else:
            no = net * s[i]
            stc = np.where(no >= 30, 2, np.where(no <= -30, 0, 1))
            p = tab[wal[i]][stc]
            draw = rng.random(Rr) < p
            if variant == 3:
                L_ = ucoup[i] < p
            else:
                L_ = np.where(stc == obs_state[i], lg[i], draw) if variant == 1 else draw
        sh = np.where(L_, big[i], mode[i]) * frac[i] * fill
        x = sh * (won[i] - cps[i])
        pnl[:, cur] += x; pnl_w[wal[i], :, cur] += x
        net += sh * s[i]
    return pnl, pnl_w, uw


def corr_stats(P, actual):
    rr = [np.corrcoef(P[2 * k], P[2 * k + 1])[0, 1] for k in range(P.shape[0] // 2)]
    rs = [spearmanr(P[2 * k], P[2 * k + 1]).statistic for k in range(min(40, P.shape[0] // 2))]
    ra = [np.corrcoef(P[k], actual)[0, 1] for k in range(P.shape[0])]
    rsa = [spearmanr(P[k], actual).statistic for k in range(min(40, P.shape[0]))]
    return {"r_replay_replay": round(float(np.nanmean(rr)), 4), "rho_replay_replay": round(float(np.nanmean(rs)), 4),
            "r_replay_wallet": round(float(np.nanmean(ra)), 4), "rho_replay_wallet": round(float(np.nanmean(rsa)), 4)}


def main(out):
    o, mode = orders()
    res = {"menu_mode_by_day": mode}
    B = o[(o.w >= BUILD[0]) & (o.w < BUILD[1])].copy().reset_index(drop=True)
    V = o[(o.w >= VAL[0]) & (o.w < VAL[1])].copy().reset_index(drop=True)
    res["decomposition_VALIDATE"] = {"pooled": decomposition(V), **{w: decomposition(V, w) for w in ("DS", "GF", "XM")}}
    mid = (VAL[0] + VAL[1]) // 2
    res["decomposition_VALIDATE_halves"] = {"first": decomposition(V[V.w < mid]), "second": decomposition(V[V.w >= mid])}
    stV = observed_states(V); stB = observed_states(B)
    res["P(large | state)_VALIDATE"] = {nm: round(float(V.large.to_numpy()[stV == k].mean()), 4) for k, nm in ((0, "short_o"), (1, "flat"), (2, "long_o"))}
    res["state_of_large_orders_VALIDATE"] = {nm: round(float((stV[V.large.to_numpy()] == k).mean()), 4) for k, nm in ((0, "short_o"), (1, "flat"), (2, "long_o"))}
    tab = {}
    for wi, wl in enumerate(("DS", "GF", "XM")):
        sel = (B.wallet == wl).to_numpy()
        tab[wi] = np.array([float(B.large.to_numpy()[sel & (stB == k)].mean()) if (sel & (stB == k)).any() else 0.1 for k in (0, 1, 2)])
    res["BUILD_P(large | state, wallet)"] = {wl: [round(float(x), 4) for x in tab[i]] for i, wl in enumerate(("DS", "GF", "XM"))}
    actual = V.groupby("w").x.sum()
    act_w = {wl: V[V.wallet == wl].groupby("w").x.sum() for wl in ("DS", "GF", "XM")}
    rng = np.random.default_rng(10)
    res["replays"] = {}
    for q in (0.61, 0.70):
        uc = coupled_u(V, tab, stV, np.random.default_rng(33))
        for vi, vn in VARIANTS:
            P, Pw, uw = replay(V, tab, q, vi, rng, stV, uc)
            a = actual.reindex(uw).to_numpy()
            row = {"pooled": corr_stats(P, a)}
            for wi, wl in enumerate(("DS", "GF", "XM")):
                aw = act_w[wl].reindex(uw).fillna(0).to_numpy()
                has = np.isin(uw, act_w[wl].index)
                row[wl] = corr_stats(Pw[wi][:, has], aw[has])
            res["replays"][f"q={q} {vn}"] = row
            print(q, vn, json.dumps(row), flush=True)
    json.dump(res, open(out, "w"), indent=1, default=lambda x: x.item() if hasattr(x, "item") else str(x))
    print(json.dumps({k: v for k, v in res.items() if k != "replays"}, indent=1, default=str)[:4000])


if __name__ == "__main__":
    if len(sys.argv) > 2:
        VARIANTS = tuple(v for v in VARIANTS if str(v[0]) in sys.argv[2].split(","))
    main(sys.argv[1])

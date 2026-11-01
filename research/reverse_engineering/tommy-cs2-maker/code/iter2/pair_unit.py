"""Mechanics panel X12: take-then-make pair unit. Parent = each wallet taker order (team X, signing s). Children = the
wallet's maker orders on the complement token signed in [s + 0.5, s + 5] s (the re-pair bids posted after its own FAK
is matched, 1-s in-play delay). Unit PnL at settlement = parent fills + children fills (shares x payout - USDC; fees
and rebates excluded). Compared with the parent leg alone; event-level bootstrap (4000) per split.
Development data 16-22 Oct only (outcomes used for settlement only)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from common import OUT, RES, SPLIT, WALLET  # noqa: E402


def main():
    u = pd.read_parquet(OUT / "universe.parquet")
    pay = {}
    for cid, r in zip(u.cid, u.res_outcome_prices):
        try:
            pay[cid] = float(json.loads(r)[0])
        except Exception:  # noqa: BLE001
            pass
    cd = pd.read_parquet(OUT / "calldata_all.parquet")
    w = cd[(cd.maker == WALLET) & cd.cid.isin(pay)].copy()
    w["pay"] = np.where(w.oi == 0, w.cid.map(pay), 1 - w.cid.map(pay))
    w["usdc"] = w.fill * w.price  # BUY at its limit price (maker exact; taker approx.)
    w["pnl"] = w.fill * w.pay - w.usdc
    w["role"] = np.where(w.idx == -1, "taker", "maker")
    key = ["cid", "oi", "role", "sign_ms", "price", "shares"]
    o = w.groupby(key, as_index=False).agg(fill=("fill", "sum"), usdc=("usdc", "sum"), pnl=("pnl", "sum"), event=("event", "first"), gs=("gs_ts", "first"))
    tk = o[o.role == "taker"].sort_values("sign_ms")
    mk = o[o.role == "maker"]
    rows = []
    for cid, g in tk.groupby("cid"):
        m = mk[mk.cid == cid]
        for r in g.itertuples():
            ch = m[(m.oi != r.oi) & (m.sign_ms >= r.sign_ms + 500) & (m.sign_ms <= r.sign_ms + 5000)]
            same = m[(m.oi == r.oi) & (m.sign_ms >= r.sign_ms + 500) & (m.sign_ms <= r.sign_ms + 5000)]
            rows.append({"cid": cid, "event": r.event, "gs": r.gs, "parent_pnl": r.pnl, "parent_usd": r.usdc, "parent_sh": r.fill,
                         "child_pnl": ch.pnl.sum(), "child_usd": ch.usdc.sum(), "child_sh": ch.fill.sum(), "n_child": len(ch),
                         "same_pnl": same.pnl.sum(), "pair_cost": (r.usdc / r.fill + (ch.usdc.sum() / ch.fill.sum())) if (r.fill > 0 and ch.fill.sum() > 0) else np.nan})
    x = pd.DataFrame(rows)
    x["unit_pnl"] = x.parent_pnl + x.child_pnl
    rng = np.random.default_rng(4)
    res = {"parents": len(x), "with_children": int((x.n_child > 0).sum()), "child_shares_over_parent": round(float(x.child_sh.sum() / x.parent_sh.sum()), 3),
           "pair_cost_q": x.pair_cost.quantile([.25, .5, .75]).round(3).tolist()}
    for sp, s in (("BUILD", x[x.gs < SPLIT]), ("VALIDATE", x[x.gs >= SPLIT])):
        ev = s.groupby("event").agg(p=("parent_pnl", "sum"), c=("child_pnl", "sum"), u=("unit_pnl", "sum"), pu=("parent_usd", "sum"), cu=("child_usd", "sum"))
        out = {"events": len(ev), "parent_pnl": round(float(ev.p.sum()), 0), "child_pnl": round(float(ev.c.sum()), 0), "unit_pnl": round(float(ev.u.sum()), 0),
               "parent_ret": round(float(ev.p.sum() / ev.pu.sum()), 4), "unit_ret": round(float(ev.u.sum() / (ev.pu.sum() + ev.cu.sum())), 4)}
        for col in ("p", "u"):
            b = []
            for _ in range(4000):
                i = rng.integers(0, len(ev), len(ev))
                b.append(ev[col].to_numpy()[i].sum())
            b = np.array(b)
            out[f"{col}_ci95"] = [round(float(np.quantile(b, .025)), 0), round(float(np.quantile(b, .975)), 0)]
            out[f"{col}_p_le0"] = round(float((b <= 0).mean()), 4)
        res[sp] = out
    json.dump(res, open(RES / "results/pair_unit.json", "w"), indent=1)
    print(json.dumps(res, indent=1))


if __name__ == "__main__":
    main()

"""X143 (panel iter12 assumptions P4): read the configuration online from the most recent development-pattern block.

Lot 10-23..30 (STUDY 10-23..26 case by case; VALIDATE 10-27..30 aggregate only). The real calendar is emulated on the
lot: block j of day d (days since 10-23) is 'sealed-pattern' iff d + j is odd. For every sealed-pattern block B the
procedure reads the cluster's fills of the most recent development-pattern block P before B (own history) and fixes:
  k_P   the Chainlink posture multiplier in {0.5, 0.7, 1.0, 1.4, 2.0, 3.0} with the best accuracy on P's
        not-decided fills (variant 'entry': P's entry fills only, cluster position 0);
  dec_P the decided-window branch: cheaper token or favourite, whichever was better on P's decided fills;
  fallback to the frozen constants (k 1.4, cheaper) when P has fewer than MIN_N fills in the branch.
Applied to B and compared with the frozen R8 public side (decided -> cheaper, else posture with k 1.4) per fill and at
the first fill of every window's first run (entry run). 2-h block bootstrap (2,000 draws) of the gain on each half.
Inputs: it12/typed_fills.parquet (block clock, real Chainlink seconds where present: cl, Kg, v300, tau_cl, mid_up,
inv_c = cluster net Up-minus-Down shares before the fill).
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import norm

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
D0 = 1792713600
KS = (0.5, 0.7, 1.0, 1.4, 2.0, 3.0)
MIN_N = 30
VAL0 = 1793059200


def main():
    d = pd.read_parquet(ROOT / ".cache/re/directional-maker/it12/typed_fills.parquet")
    d = d[d.cl.notna() & d.Kg.notna() & d.v300.notna() & d.tau_cl.notna() & d.mid_up.notna()].copy()
    x = np.log(d.cl.to_numpy(float) / d.Kg.to_numpy(float)) / (d.v300.to_numpy(float) * np.sqrt(np.maximum(d.tau_cl.to_numpy(float), 1.0)))
    for k in KS:
        d[f"post_{k}"] = norm.cdf(x / k) > d.mid_up.to_numpy()
    d["y"] = d.is_up == 1
    d["dec"] = (d.mid_up - 0.5).abs() > 0.4
    d["cheap"] = d.mid_up < 0.5
    d["entry"] = (d.inv_c == 0) & ~d.dec
    d["blk"] = (d.st - D0) // 21600
    d["dd"] = (d.st - D0) // 86400
    d["jj"] = ((d.st - D0) % 86400) // 21600
    d["sealed_pattern"] = ((d.dd + d.jj) % 2) == 1
    d["frozen"] = np.where(d.dec, d.cheap, d["post_1.4"])
    d = d.sort_values(["cid", "b"], kind="stable")
    d["run"] = d.groupby("cid").is_up.transform(lambda s: (s != s.shift()).cumsum())
    blocks = sorted(set(d.blk))
    dev = [b for b in blocks if not d[d.blk == b].sealed_pattern.iloc[0]]
    rows, params = [], {}
    for B in blocks:
        g = d[d.blk == B]
        if not g.sealed_pattern.iloc[0]:
            continue
        prev = [b for b in dev if b < B]
        if not prev:
            continue
        P = d[d.blk == prev[-1]]
        out = {}
        for var, mask in (("all", ~P.dec), ("entry", P.entry)):
            pm = P[mask]
            if len(pm) >= MIN_N:
                accs = {k: float((pm[f"post_{k}"] == pm.y).mean()) for k in KS}
                out[var] = max(accs, key=accs.get)
            else:
                out[var] = 1.4
        pdx = P[P.dec]
        dec_side = "cheaper"
        if len(pdx) >= MIN_N:
            dec_side = "cheaper" if (pdx.cheap == pdx.y).mean() >= (~pdx.cheap == pdx.y).mean() else "favourite"
        params[int(B)] = {"from_block": int(prev[-1]), "k_all": out["all"], "k_entry": out["entry"], "dec": dec_side, "n_prev": int(len(P))}
        dec_pred = g.cheap if dec_side == "cheaper" else ~g.cheap
        g = g.assign(online_all=np.where(g.dec, dec_pred, g[f"post_{out['all']}"]),
                     online_entry=np.where(g.dec, dec_pred, g[f"post_{out['entry']}"]),
                     online_k_only=np.where(g.dec, g.cheap, g[f"post_{out['all']}"]))
        rows.append(g)
    E = pd.concat(rows)
    E["half"] = np.where(E.st >= VAL0, "validate", "study")
    E["b2h"] = (E.st - D0) // 7200
    first = E[E.run == 1].groupby("cid").head(1)
    res = {"params": params}
    rng = np.random.default_rng(13)
    for half, g in E.groupby("half"):
        o = {"n_fills": int(len(g)), "blocks": int(g.blk.nunique())}
        for r in ("frozen", "online_all", "online_entry", "online_k_only", "cheap"):
            o[r] = float((g[r] == g.y).mean())
        f1 = first[first.half == half]
        o["entry_run_n"] = int(len(f1))
        for r in ("frozen", "online_all", "online_entry", "online_k_only"):
            o[f"entry_run_{r}"] = float((f1[r] == f1.y).mean()) if len(f1) else None
        # 2-h block bootstrap of the per-fill gain online_all - frozen
        gg = g.assign(dlt=(g.online_all == g.y).astype(float) - (g.frozen == g.y).astype(float))
        agg = gg.groupby("b2h").dlt.agg(["sum", "size"])
        s, n = agg["sum"].to_numpy(), agg["size"].to_numpy()
        bs = []
        for _ in range(2000):
            i = rng.integers(0, len(s), len(s))
            bs.append(s[i].sum() / n[i].sum())
        o["gain_online_all"] = float(s.sum() / n.sum())
        o["gain_ci95"] = [float(np.percentile(bs, 2.5)), float(np.percentile(bs, 97.5))]
        o["gain_p_le_0"] = float(np.mean(np.asarray(bs) <= 0))
        o["per_wallet"] = {w: {"frozen": float((x.frozen == x.y).mean()), "online_all": float((x.online_all == x.y).mean()), "n": int(len(x))}
                           for w, x in g.groupby("w")}
        res[half] = o
    print(json.dumps(res, indent=1, default=float))
    (HERE.parent / "results/iter13_online_config.json").write_text(json.dumps(res, indent=1, default=float))


if __name__ == "__main__":
    main()

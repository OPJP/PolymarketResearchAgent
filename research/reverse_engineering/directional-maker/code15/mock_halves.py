"""iteration 15, T6 (X174, assumptions P2, light form): the examiner's earlier/later halves on mock weekend lots
(Sat 06-12 + Sat 18-24 + Sun 00-06 UTC of 10-10/11 and 10-17/18 (BUILD) and 10-24/25 (STUDY)). Halves by window start:
earlier = Sat 06-12 + Sat 18-21, later = Sat 21-24 + Sun 00-06 (listings are uniform in time, so this is the median
listed start). Per half: R8 universe (BTC 5m + 15m) share of cluster trades and $, per wallet; the non-BTC side rules
(in-the-money at the open, posture k 1.0 with the fill-price proxy later)."""
import json, sys
from pathlib import Path
import numpy as np, pandas as pd
from scipy.stats import norm
HERE = Path(__file__).resolve().parent; sys.path.insert(0, str(HERE))
from nb_side import C, RES, parse, dev_activity
a = dev_activity()
a = a[a.side == "BUY"].copy()
P = a.slug.map(lambda s: parse(str(s))); a = a[P.notna()].copy(); P = P[P.notna()]
a["fam"] = [p[0] for p in P]; a["st"] = [p[2] for p in P]
a["u1"] = a.fam.isin(["btc-5m", "btc-15m"])
nb = pd.read_parquet(C / "it15_nb_side.parquet")
out = {}
for sat in ("2026-10-10", "2026-10-17", "2026-10-24"):
    s0 = int(pd.Timestamp(sat, tz="UTC").timestamp())
    early = [(s0 + 6 * 3600, s0 + 12 * 3600), (s0 + 18 * 3600, s0 + 21 * 3600)]
    late = [(s0 + 21 * 3600, s0 + 24 * 3600), (s0 + 24 * 3600, s0 + 30 * 3600)]
    for hn, iv in (("early", early), ("late", late)):
        m = np.zeros(len(a), bool)
        for x, y in iv:
            m |= (a.st >= x) & (a.st < y)
        g = a[m]
        row = {"trades": int(len(g)), "usd": round(float(g.usdcSize.sum()), 1),
               "U1_trades": round(float(g.u1.mean()), 3) if len(g) else None,
               "U1_usd": round(float(g.loc[g.u1, "usdcSize"].sum() / max(g.usdcSize.sum(), 1e-9)), 3) if len(g) else None,
               "per_wallet_U1_trades": {w: round(float(x.u1.mean()), 3) for w, x in g.groupby("wallet")},
               "per_wallet_trades": g.groupby("wallet").size().to_dict()}
        mm = np.zeros(len(nb), bool)
        for x, y in iv:
            mm |= (nb.st >= x) & (nb.st < y)
        h = nb[mm & ~nb.btc_core & nb.rule_ok.notna()]
        row["nonbtc_n"] = int(len(h))
        row["nonbtc_itm_open"] = [round(float(h[h.phase == "open<20s"].rule_ok.mean()), 3) if (h.phase == "open<20s").any() else None, int((h.phase == "open<20s").sum())]
        row["nonbtc_itm_all"] = round(float(h.rule_ok.mean()), 3) if len(h) else None
        row["nonbtc_mktfav_all"] = round(float(h.mktfav_ok.mean()), 3) if len(h) else None
        out[f"{sat}_{hn}"] = row
        print(sat, hn, {k: v for k, v in row.items() if k not in ("per_wallet_trades",)})
(RES / "iter15_mock_halves.json").write_text(json.dumps(out, indent=1, default=float))

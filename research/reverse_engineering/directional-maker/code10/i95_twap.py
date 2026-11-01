"""Iteration 10 (I9-5 = X91): mo-money's third input, candidate (b) the RTDS Chainlink TWAP-60 topic (never scored per
wallet). Same unit and code as code9/posture_at_add.py (iteration-6 confirmed filled orders of 10-31 14:04-16:13 UTC, the
posture at the raw-book ADD time and at the MATCH time), with the reference = Chainlink report (frozen) or the TWAP-60
value stamped floor((t - 1432)/1000) (dm_rtds crypto_prices_twap_sixty). Signature: one candidate lifts mo-money's 500s
to >= 0.80 at the add while moving the other wallets' 500s by <= 0.02."""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import norm

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
sys.path.insert(0, str(HERE.parent / "code5"))
sys.path.insert(0, str(HERE.parent / "code6"))
import rawread  # noqa: E402
from pres_live import load_ref  # noqa: E402

C = ROOT / ".cache/re/directional-maker"
a, b = 1793455600, 1793463203


def twap_series():
    out = {}
    for p in sorted((ROOT / ".cache/live/dev/dm_rtds").glob("*.jsonl.gz")):
        for chunk in rawread._members(p.read_bytes()):
            for line in chunk.split(b"\n"):
                if b"twap_sixty" not in line:
                    continue
                try:
                    r = json.loads(line)
                    j = json.loads(r["m"])
                except (ValueError, KeyError, TypeError):
                    continue
                pl = j.get("payload") or {}
                if str(pl.get("symbol", "btc")).lower() not in ("btc", "btc/usd", "btcusd"):
                    continue
                for x in pl.get("data", []) or []:
                    try:
                        out.setdefault(int(x["timestamp"]) // 1000, float(x["value"]))
                    except (KeyError, TypeError, ValueError):
                        pass
    return out


def main():
    Q = pd.read_parquet(C / "it6" / f"confirmed_{a}_{b}.parquet")
    Q = Q[Q.found].drop_duplicates(["wallet", "ms", "add_s"]).copy()
    tch = pd.read_parquet(C / "it6" / f"touch_{a}_{b}.parquet")
    fu, cl, tw = load_ref(a, b)
    twv = twap_series()
    sp = pd.read_parquet(C / "it9" / "spot1s_rest_1793440800_1793469600.parquet").sort_values("sec")
    b0 = int(sp.sec.iloc[0])
    px = np.full(int(sp.sec.iloc[-1]) - b0 + 1, np.nan)
    px[sp.sec.astype(int).to_numpy() - b0] = sp.px.to_numpy()
    px = pd.Series(px).ffill().to_numpy()
    rr = np.r_[0.0, np.diff(np.log(px))]
    cs = np.r_[0.0, np.cumsum(rr * rr)]
    tg = {w: g.sort_values("s") for w, g in tch.groupby("w")}
    rows = []
    for r in Q.itertuples(index=False):
        st = int(r.slug.rsplit("-", 1)[1])
        L = 900 if "-15m-" in r.slug else 300
        K = tw.get(st)
        g = tg.get(r.slug)
        if K is None or g is None:
            continue
        ts_, bb_, ba_ = g.s.to_numpy(), g.bb.to_numpy(), g.ba.to_numpy()
        rec = {"wallet": r.wallet, "S": r.S, "up": int(r.side == 1)}
        for nm, t in (("add", int(r.add_s)), ("match", int(r.ms))):
            i = np.searchsorted(ts_, t, side="left") - 1
            k = t // 1000 - 1 - b0
            sg = 1.4 * np.sqrt((cs[k + 1] - cs[k + 1 - 300]) / 300)
            tau = max(st + L - t / 1000, 1.0)
            for ref, src in (("cl", cl), ("tw", twv)):
                c = src.get((t - 1432) // 1000)
                if c is None or i < 0:
                    rec[f"{nm}_{ref}"] = np.nan
                    continue
                fair = norm.cdf(np.log(c / K) / (sg * np.sqrt(tau)))
                rec[f"{nm}_{ref}"] = int(fair > (bb_[i] + ba_[i]) / 2)
        rows.append(rec)
    D = pd.DataFrame(rows).dropna()
    out = {"n": int(len(D)), "twap_seconds": len(twv)}
    for w, g in D.groupby("wallet"):
        for cls, k in (("500", np.isclose(g.S, 500)), ("other", ~np.isclose(g.S, 500))):
            h = g[k]
            if len(h) < 15:
                continue
            out[f"{w}|{cls}"] = {"n": int(len(h)), **{c: round(float((h[c] == h.up).mean()), 3) for c in ("add_cl", "add_tw", "match_cl", "match_tw")}}
    print(json.dumps(out, indent=1))
    json.dump(out, open(ROOT / "research/reverse_engineering/directional-maker/results/iter10_i95_twap.json", "w"), indent=1)


if __name__ == "__main__":
    main()

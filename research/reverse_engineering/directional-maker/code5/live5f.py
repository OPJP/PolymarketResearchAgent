"""Live lab part f: is the cluster filled exactly when a fingerprinted (500/100) order rests at the hit level?
For each trade (x record): hit level in the Up book; resting fingerprint order there (an add of 500/100 not yet
removed by an equal-size removal, added within the last 3 s); label = the trade's tx holds a cluster fill."""
import glob, json, sys
from pathlib import Path
import numpy as np, pandas as pd
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import live5  # noqa
C = HERE.parents[3] / ".cache/re/directional-maker"

def main(a, b):
    ev, tr, bk = live5.load_clob(a, b)
    acts = pd.concat([pd.read_parquet(p) for p in glob.glob(str(C / "live_activity_*.parquet"))])
    acts = acts[acts.type == "TRADE"]
    amax = acts.timestamp.max()
    ctx = set(acts.transactionHash.str.lower())
    tr = tr[(tr.s >= a * 1000) & (tr.s < min(b, amax - 5) * 1000)].copy()
    tr["side"] = np.where(tr.ai == 0, np.where(tr.d == "BUY", 0, 1), np.where(tr.d == "BUY", 1, 0))
    tr["lvl"] = np.where(tr.ai == 0, tr.p, 1 - tr.p).round(2)
    tr["clu"] = tr.h.isin(ctx)
    f = ev[(np.abs(np.abs(ev.d) - 500) < 0.01) | (np.abs(np.abs(ev.d) - 100) < 0.01)]
    g = {k: (x.s.to_numpy(), x.d.to_numpy()) for k, x in f.groupby(["w", "side", "p"])}
    rest = []
    for r in tr.itertuples(index=False):
        x = g.get((r.w, r.side, r.lvl))
        st = "none"
        if x is not None:
            s_, d_ = x
            i = np.searchsorted(s_, r.s, side="right")
            live = {}
            for k in range(max(0, i - 50), i):
                S = round(abs(d_[k]))
                if d_[k] > 0 and r.s - s_[k] <= 3000:
                    live[S] = live.get(S, 0) + 1
                elif d_[k] < 0 and live.get(S, 0) > 0:
                    live[S] -= 1
            if live.get(500, 0) > 0:
                st = "500"
            elif live.get(100, 0) > 0:
                st = "100"
        rest.append(st)
    tr["rest"] = rest
    res = {"period": [a, int(min(b, amax - 5))], "trades": int(len(tr)), "cluster_trades": int(tr.clu.sum()),
           "by_resting_state": {k: {"n": int(len(v)), "p_cluster": round(float(v.clu.mean()), 4)} for k, v in tr.groupby("rest")},
           "cluster_trades_by_state": tr[tr.clu].rest.value_counts().to_dict()}
    print(json.dumps(res, indent=1))
    (HERE.parent / "results" / f"iter5_live_f_{a}_{b}.json").write_text(json.dumps(res, indent=1))

if __name__ == "__main__":
    main(int(sys.argv[1]), int(sys.argv[2]))

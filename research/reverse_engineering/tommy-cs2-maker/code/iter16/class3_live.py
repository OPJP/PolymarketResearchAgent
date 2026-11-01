"""X229 step 3 (assumptions panel iter-15 P3): on BUILD-live (10-31 12-18), is the level of its class-3 value changes
(adds 1.04-3 s after a wallet-free group-P take on the event, i.e. after that take's CLOB match) a post-trade book
quantity? Adds and their book state from iter12/slot_vrel_rows (server clock); takes from calldata_dev (signing ms).
Within one tick (1c) of V_after for: J at the add (others' best bid after the trade), ask - 1c, and the take's limit
price expressed on the add's token (p if same token, 1 - p if the complement). Classes 1-2 (0-1.04 s) for comparison.
Output: results/class3_live.json"""
import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[5]
OUT = ROOT / ".cache/re/tommy-cs2-maker"
RES = ROOT / "research/reverse_engineering/tommy-cs2-maker/results"
gp = set(json.load(open(ROOT / "research/reverse_engineering/tommy-cs2-maker/code/final_rule_v5_groupP.json"))["members"])
r = pd.read_parquet(OUT / "iter12/slot_vrel_rows.parquet")
r = r[(r.kind == "add") & r.V_after.notna() & r.J.notna() & r.spread.notna() & r.dV.notna() & (r.dV.abs() >= 0.01 - 1e-9)].copy()
r["ask"] = r.J + r.spread / 100
r["event"] = r.slug.str.replace(r"-game\d$", "", regex=True)
tok_ev = dict(zip(r.a.astype(str), r.event))
c = pd.read_parquet(OUT / "calldata_dev.parquet")
W = "0x0063b23cdeb43166d6c0246c05baaf9b9bd72dd2"
wtx = set(c.loc[c.maker.str.lower() == W, "tx"])
tk = c[(c.idx == -1) & c.maker.str.lower().isin(gp) & ~c.tx.isin(wtx) & (c.sign_ms >= 1793448000000) & (c.sign_ms < 1793469600000)].drop_duplicates("tx").copy()
tk["event"] = tk.token_id.astype(str).map(tok_ev)
tk = tk[tk.event.notna()].sort_values("sign_ms")
rows = []
for ev, g in r.groupby("event"):
    t_ = tk[tk.event == ev]
    if not len(t_):
        continue
    s = t_.sign_ms.to_numpy(float)
    for x in g.itertuples():
        j = np.searchsorted(s, x.t, side="right") - 1
        if j < 0:
            continue
        lag = x.t - s[j]
        if lag > 3000:
            continue
        q = t_.iloc[j]
        p_tok = float(q.price) if str(q.token_id) == str(x.a) else 1 - float(q.price)
        rows.append({"cls": "class3" if lag >= 1040 else "class12", "lag": lag, "V": x.V_after, "J": x.J, "askm1": x.ask - 0.01, "ptake": p_tok})
R = pd.DataFrame(rows)
out = {"adds_with_take_in_3s": int(len(R)), "takes": int(len(tk))}
for cl, g in R.groupby("cls"):
    w = lambda a: round(float((np.abs(np.round((g.V - a) * 100)) <= 1).mean()), 3)  # noqa: E731
    out[cl] = {"n": int(len(g)), "w1_J": w(g.J), "w1_ask_m1": w(g.askm1), "w1_take_price": w(g.ptake),
               "w1_take_price_m1": w(g.ptake - 0.01), "w1_best_of_three_oracle": round(float(np.mean([min(abs(round((v - a) * 100)) for a in (j_, k_, p_)) <= 1 for v, j_, k_, p_ in zip(g.V, g.J, g.askm1, g.ptake)])), 3)}
(RES / "class3_live.json").write_text(json.dumps(out, indent=1))
print(json.dumps(out, indent=1))

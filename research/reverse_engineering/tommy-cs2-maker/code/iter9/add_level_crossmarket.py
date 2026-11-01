"""Iteration 9, finding 14 follow-up: is the information in the wallet's add level PUBLIC on a sibling book? For own
validated adds on a book whose event has another recorded book (match <-> map), Spearman of the add's offset from its
own book's others' mid with (a) the sibling book's others'-mid change over (s - 2 s, s - 0.1 s] for the same team, and
(b) its own book's others'-mid change over the same window; also the add offset vs the sibling's FUTURE move
(s - 0.1 s, s + 10 s]. Team alignment from the Gamma outcomes. Output: results/add_level_crossmarket.json"""
import json, sys, re
from pathlib import Path
import numpy as np, pandas as pd
from scipy.stats import spearmanr
ROOT = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(ROOT))
from polyrea.adapters.polymarket import PolymarketData
OUT = ROOT / ".cache/re/tommy-cs2-maker"; RES = ROOT / "research/reverse_engineering/tommy-cs2-maker/results"
def norm(s): return re.sub(r"[^a-z0-9]", "", str(s).lower())
A = pd.read_parquet(OUT / "linked_adds_dev.parquet")
A["vown"] = (A.owner == "wallet") | (A.F_mkt & (A.in_burst | (A["size"] != 100)))
A = A[A.kind == "add"]
dm = pd.read_parquet(OUT / "dev_markets.parquet")
mk, _ = PolymarketData().markets_by_condition(sorted(dm.cid))
tok_info = {}
for r in dm.itertuples():
    x = mk.get(r.cid) or {}
    outs = json.loads(x["outcomes"]) if isinstance(x.get("outcomes"), str) else (x.get("outcomes") or [])
    if len(outs) == 2:
        tok_info[str(r.tok0)] = (r.event, r.slug, norm(outs[0])[:5], norm(outs[1])[:5])
M = pd.read_parquet(OUT / "others_mid_dev.parquet").sort_values(["a", "s"])
mids = {str(a): (g.s.to_numpy(float), g.mid.to_numpy(float)) for a, g in M.groupby("a")}
by_event = {}
for a, (ev, slug, o0, o1) in tok_info.items():
    if a in mids:
        by_event.setdefault(ev, []).append((a, slug, o0, o1))
def m_at(a, t):
    ts, md = mids[a]; j = np.searchsorted(ts, t, side="right") - 1
    return md[j] if j >= 0 else np.nan
rows = []
for r in A[A.vown].itertuples():
    a = str(r.a)
    if a not in tok_info or a not in mids: continue
    ev, slug, o0, o1 = tok_info[a]
    sibs = [x for x in by_event.get(ev, []) if x[0] != a]
    if not sibs: continue
    tok0 = r.side == "BUY"
    team = o0 if tok0 else o1
    m0 = m_at(a, r.s - 100)
    if not np.isfinite(m0): continue
    mt = m0 if tok0 else 1 - m0
    off = ((r.p if tok0 else 1 - r.p) - mt) * 100
    own_pre = (m_at(a, r.s - 100) - m_at(a, r.s - 2000)) * 100 * (1 if tok0 else -1)
    for sa, sslug, so0, so1 in sibs:
        sg = 1 if team == so0 else (-1 if team == so1 else 0)
        if sg == 0: continue
        pre = (m_at(sa, r.s - 100) - m_at(sa, r.s - 2000)) * 100 * sg
        fut = (m_at(sa, r.s + 10000) - m_at(sa, r.s - 100)) * 100 * sg
        rows.append({"off": off, "sib_pre": pre, "own_pre": own_pre, "sib_fut": fut})
X = pd.DataFrame(rows).replace([np.inf, -np.inf], np.nan).dropna()
X = X[X.off.abs() <= 15]
res = {"pairs": int(len(X)),
       "spearman_off_vs_sibling_pre2s": round(float(spearmanr(X.off, X.sib_pre)[0]), 4),
       "spearman_off_vs_own_book_pre2s": round(float(spearmanr(X.off, X.own_pre)[0]), 4),
       "spearman_off_vs_sibling_future10s": round(float(spearmanr(X.off, X.sib_fut)[0]), 4),
       "share_sibling_pre_moved_ge1c": round(float((X.sib_pre.abs() >= 1).mean()), 4)}
print(json.dumps(res, indent=1)); json.dump(res, open(RES / "add_level_crossmarket.json", "w"), indent=1)

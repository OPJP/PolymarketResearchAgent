"""iteration 15 (X170 / X168 on the current development block): the cluster's filled orders on 11-01 06:00-now from
calldata (original size and limit price of every cluster maker order in its fill transactions), by family."""
import glob, json, sys, collections
from pathlib import Path
import pandas as pd
HERE = Path(__file__).resolve().parent; ROOT = HERE.parents[3]; sys.path.insert(0, str(HERE.parent / "code4"))
import calldata as cd
W = {"0xc2ad03f79ca3f3c17d8c7de2612ce0c89b7d40ed", "0x3725d52f3c252e8374999cc8617292ea2608ad88", "0x32ed2e546b187ca15e2841edc82b22c713cf8ec3"}
fr = [pd.read_parquet(f) for f in glob.glob(str(ROOT / ".cache/re/directional-maker/act15_*_1793512800_*.parquet"))]
a = pd.concat(fr); a = a[a.type == "TRADE"]
a["fam"] = a.slug.str.replace(r"-\d+$", "", regex=True).str.replace(r"-(october|november).*", "", regex=True)
tx2fam = dict(zip(a.transactionHash.str.lower(), a.fam)); tx2t = dict(zip(a.transactionHash.str.lower(), a.timestamp))
rows = []
for h, tx in cd.fetch_txs(sorted(tx2fam)):
    d = cd.decode(tx["input"]) if tx else None
    if not d:
        continue
    for m in d["makers"]:
        if m["maker"].lower() in W and m["oside"] == 0:
            sh = m["taker_amount"] / 1e6; px = m["maker_amount"] / max(m["taker_amount"], 1)
            rows.append((h, tx2fam[h], tx2t[h], m["maker"][:6], round(sh, 2), round(px, 3), m["sign_ms"], m["salt"][-6:]))
    t = d["taker"]
    if t["maker"].lower() in W:
        rows.append((h, tx2fam[h], tx2t[h], "TAKER" + t["maker"][:4], round((t["taker_amount"] if t["oside"] == 0 else t["maker_amount"]) / 1e6, 2), None, t["sign_ms"], t["salt"][-6:]))
D = pd.DataFrame(rows, columns=["h", "fam", "t", "who", "size", "px", "sign_ms", "salt"])
D.to_parquet(ROOT / ".cache/re/directional-maker/it15_today_orders.parquet", index=False)
out = {}
for fam, g in D[~D.who.str.startswith("TAKER")].groupby("fam"):
    out[fam] = {"orders": int(g.drop_duplicates(["who", "salt"]).shape[0]), "sizes": g.drop_duplicates(["who", "salt"])["size"].value_counts().head(6).to_dict()}
out["taker_rows"] = int(D.who.str.startswith("TAKER").sum()); out["txs"] = len(tx2fam)
print(json.dumps(out, indent=1, default=str))
(HERE.parent / "results/iter15_today_orders.json").write_text(json.dumps(out, indent=1, default=str))

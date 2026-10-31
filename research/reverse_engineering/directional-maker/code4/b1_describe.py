"""B1 description on STUDY (lot first half): the cluster's filled orders from calldata."""
import sys, json
from pathlib import Path
import numpy as np, pandas as pd
ROOT = Path(__file__).resolve().parents[4]
C = ROOT / ".cache/re/directional-maker"
tag = sys.argv[1] if len(sys.argv) > 1 else "study"
W = {"0xc2ad03f79ca3f3c17d8c7de2612ce0c89b7d40ed": "bosona", "0x3725d52f3c252e8374999cc8617292ea2608ad88": "almach",
     "0x32ed2e546b187ca15e2841edc82b22c713cf8ec3": "momoney"}
d = pd.concat([pd.read_parquet(p) for p in sorted((C / "calldata").glob(f"{tag}_*.parquet"))], ignore_index=True)
print("rows", len(d), "txs", d.tx.nunique(), "roles", d.role.value_counts().to_dict())
f = pd.read_parquet(C / "exam/fills_holdout.parquet")
win = pd.read_parquet(C / "exam/windows_5m.parquet")
print(win.columns.tolist()[:30])
# block ts per tx from fills (data-api ts = block timestamp)
txts = f.groupby("txh").ts.min()
d["bts"] = d.tx.map(txts)
d["shares"] = np.where(d.oside == 0, d.taker_amount, d.maker_amount) / 1e6
d["usdc"] = np.where(d.oside == 0, d.maker_amount, d.taker_amount) / 1e6
d["lim"] = d.usdc / d.shares
d["life"] = d.bts - d.sign_ms / 1000.0
d["clu"] = d.maker.isin(list(W))
for role in ("maker", "taker"):
    for clu in (True, False):
        x = d[(d.role == role) & (d.clu == clu)]
        if len(x) == 0:
            continue
        q = x.life.quantile([0.01, 0.1, 0.25, 0.5, 0.75, 0.9, 0.99]).round(2).to_dict()
        print(role, "cluster" if clu else "other", len(x), "life q", q, "neg share", round((x.life < -0.001).mean(), 4))
cm = d[(d.role == "maker") & d.clu].copy()
cm["w"] = cm.maker.map(W)
print("sig_type by wallet", cm.groupby("w").sig_type.value_counts().to_dict())
print("sig_len by wallet", cm.groupby("w").sig_len.value_counts().to_dict())
print("signer==maker by wallet", cm.assign(s=cm.signer == cm.maker).groupby("w").s.mean().to_dict())
print("signers", cm.groupby("w").signer.unique().apply(lambda a: list(a)[:3]).to_dict())
print("metadata", cm.metadata.value_counts().head(5).to_dict())
print("builder", cm.builder.value_counts().head(5).to_dict())
print("salt digits", cm.salt.str.len().value_counts().head(8).to_dict())
# orders: unique by (maker, salt)
o = cm.drop_duplicates(["maker", "salt", "token_id"])
print("unique cluster orders", len(o), "of rows", len(cm))
print("orig size q", o.shares.quantile([0.1, 0.25, 0.5, 0.75, 0.9]).to_dict())
print("orig size top", o.shares.round(2).value_counts().head(15).to_dict())
print("size >= 50 share", round((o.shares >= 50).mean(), 3), "by usd", round(o.loc[o.shares >= 50, "usdc"].sum() / o.usdc.sum(), 3))
print("limit on 0.01 grid", round((np.abs(o.lim * 100 - np.round(o.lim * 100)) < 1e-6).mean(), 3))
# sign ms precision
print("sign_ms mod 1000 distinct share", round(o.sign_ms.mod(1000).nunique() / 1000, 3), "ms==000 share", round((o.sign_ms.mod(1000) == 0).mean(), 4))
# other makers fingerprint
om = d[(d.role == "maker") & ~d.clu]
print("other makers", om.maker.nunique(), "top", om.maker.value_counts().head(8).to_dict())
print("other builder", om.builder.value_counts().head(5).to_dict())
print("other sig_len", om.sig_len.value_counts().head(5).to_dict())
tk = d[d.role == "taker"]
print("takers sig_len", tk.sig_len.value_counts().head(5).to_dict(), "sig_type", tk.sig_type.value_counts().to_dict())
cm.to_parquet(C / f"b1_cluster_orders_{tag}.parquet")
d[d.role == "maker"].drop(columns=[c for c in ("sel",) if c in d]).to_parquet(C / f"b1_all_makers_{tag}.parquet")
d[d.role == "taker"].drop(columns=[c for c in ("sel",) if c in d]).to_parquet(C / f"b1_takers_{tag}.parquet")

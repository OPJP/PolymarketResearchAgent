"""Iteration 9 (panel iter8 assumptions P5): one process, several assets? Fingerprint search in the V2 calldata of ETH 5m,
SOL 5m and BTC 15m matches of 10-31 development windows (shared recorder clob_crypto trades with tx hashes; decoded fields
only). The btc5m-bot order factory signs ladders in bursts at rel -89.5 / +42.0 / +172.7 s of each 5m window (all four
operator wallets within ~4 s), signatureType 3, 317-byte signatures, builder = metadata = 0, salt = round(random * Date.now()).
Per maker address: orders, the share signed inside those bursts (|rel_sign - c| <= 4 s, relative to the order's own window),
signatureType / signature length / zero builder shares. Known operator wallets are labelled.
Usage: python other9.py START END OUT_JSON"""
import os, sys, json
import numpy as np, pandas as pd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import live_lab as L
import calldata

C = L.C
OPER = {"0x0ca4e9d27ff826a109ecbf74754fb66b93f277a6": "GF", "0x3048d65321be3497164cdfc2996f94f98a2e7537": "XM",
        "0xc53375ff94e96100f2b30a4b5775db35218d69a9": "DS", "0xd84403efd50b49a1d8a7181627e00307e6ea5908": "W4"}
BURSTS = (-89.5, 42.0, 172.7)
PER_WINDOW = 250


def main(a, b, out):
    tok = {}
    for r in L.recs("subs", a - 3600, b):
        if r.get("feed") != "clob_crypto":
            continue
        for slug, tks in r["markets"].items():
            for pre, kind, dur in (("eth-updown-5m-", "eth5m", 300), ("sol-updown-5m-", "sol5m", 300), ("btc-updown-15m-", "btc15m", 900),
                                   ("btc-updown-5m-", "btc5m", 300)):
                if slug.startswith(pre):
                    st = int(slug.rsplit("-", 1)[1])
                    for t in tks:
                        tok[t] = (kind, st, dur)
    tx = {}
    for r in L.recs("clob_crypto", a, b):
        if r.get("k") == "x" and r.get("a") in tok and r.get("h"):
            kind, st, dur = tok[r["a"]]
            if st >= a and st + dur <= b + 60:
                tx.setdefault((kind, st), set()).add(r["h"].lower())
    rng = np.random.default_rng(4)
    picks = {}
    for kind in ("eth5m", "sol5m", "btc15m", "btc5m"):
        ws = sorted(k for k in tx if k[0] == kind)
        sel = ws[:: max(1, len(ws) // 3)][:3] if kind != "btc15m" else ws[:2]
        for k in sel:
            h = sorted(tx[k]); h = list(rng.choice(h, min(PER_WINDOW, len(h)), replace=False))
            picks[k] = h
    hashes = [h for v in picks.values() for h in v]
    print("windows", list(picks), "txs", len(hashes), flush=True)
    rows = calldata.fetch_txs(hashes)
    df = calldata.to_frame(rows)
    h2w = {h: k for k, v in picks.items() for h in v}
    df["win"] = df.tx.str.lower().map(h2w)
    df = df[df.win.notna() & df.sign_ms.notna()].copy()
    df["kind"] = df.win.map(lambda k: k[0]); df["st"] = df.win.map(lambda k: k[1])
    df["rel_sign"] = df.sign_ms / 1000 - df.st
    dur = df.kind.map({"eth5m": 300, "sol5m": 300, "btc15m": 900, "btc5m": 300})
    # for 15m windows, the burst clock is tested against each 5-minute sub-window of the 15m window as well
    rs = df.rel_sign.to_numpy(); kd = df.kind.to_numpy()
    inb = np.zeros(len(df), bool)
    for c in BURSTS:
        inb |= np.abs(rs - c) <= 4
        inb |= (kd == "btc15m") & ((np.abs(rs - 300 - c) <= 4) | (np.abs(rs - 600 - c) <= 4))
    df["in_burst"] = inb
    df["maker"] = df.maker.str.lower()
    df["oper"] = df.maker.map(OPER)
    df["zero_bm"] = (df.builder.fillna("").str.strip("0") == "") & (df.metadata.fillna("").str.strip("0") == "")
    res = {"windows": [list(map(str, k)) for k in picks], "orders": int(len(df)), "txs": int(df.tx.nunique())}
    res["operator_orders_by_kind"] = df[df.oper.notna()].groupby(["kind", "oper"]).size().astype(int).to_dict()
    res["operator_orders_by_kind"] = {f"{k[0]}|{k[1]}": int(v) for k, v in res["operator_orders_by_kind"].items()}
    g = df.groupby(["kind", "maker"]).agg(n=("tx", "size"), burst=("in_burst", "mean"), st3=("sig_type", lambda x: float((x == 3).mean())),
                                          s317=("sig_len", lambda x: float((x == 317).mean())), zbm=("zero_bm", "mean")).reset_index()
    g["oper"] = g.maker.map(OPER)
    cand = g[(g.n >= 8) & (g.burst >= 0.6)].sort_values(["kind", "n"], ascending=[True, False])
    res["burst_makers(n>=8, burst share>=0.6)"] = [{"kind": r.kind, "maker": r.maker[:10], "n": int(r.n), "burst": round(float(r.burst), 3),
                                                     "sigtype3": round(r.st3, 3), "sig317": round(r.s317, 3), "zero_builder_meta": round(float(r.zbm), 3),
                                                     "oper": r.oper} for r in cand.itertuples()]
    res["burst_share_all_orders_by_kind"] = df.groupby("kind").in_burst.mean().round(4).to_dict()
    res["burst_share_fingerprinted(st3,317,zero_bm)_by_kind"] = df[(df.sig_type == 3) & (df.sig_len == 317) & df.zero_bm].groupby("kind").in_burst.mean().round(4).to_dict()
    # rel_sign histogram near the burst centres for non-operator fingerprinted orders on the other assets
    oth = df[df.oper.isna() & (df.sig_type == 3) & (df.sig_len == 317) & df.zero_bm & (df.kind != "btc5m")]
    res["other_assets_fingerprinted_orders"] = int(len(oth))
    res["other_assets_fingerprinted_in_burst"] = round(float(oth.in_burst.mean()), 4) if len(oth) else None
    json.dump(res, open(out, "w"), indent=1, default=str)
    print(json.dumps(res, indent=1, default=str)[:5000])


if __name__ == "__main__":
    main(int(sys.argv[1]), int(sys.argv[2]), sys.argv[3])

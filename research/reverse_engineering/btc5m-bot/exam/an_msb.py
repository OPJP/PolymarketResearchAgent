"""Examiner r1: replication of the RE's STRONGEST market-activity baseline for block-second presence, MSB of code/pres14.py
(MKT_PURE + blkaug9.AUG + capture prints: BUY count and size of others' server-ms prints on the cell's outcome and on the other
outcome in five 500-ms bins over [tau - 3500, tau - 1000), SELL count on the outcome; LightGBM train3.PARAMS, 200 rounds, positives +
30% negatives with weight 1/0.3, rng seed 14), fitted as the RE did on the development days 10-17..19 (the capture has no BUILD
days), then scored on the h1 lot's block seconds. Deviation from pres14 (stated): only the three studied wallets' transactions are
excluded from the capture prints (pres14 also excluded W4 / W5 taker txs found in the data-api tapes, which are no longer cached for
10-17..19); the frozen full model's tape features keep W4 / W5 prints too.
Writes .cache/exam/btc5m-bot/an/msb_<a>_<b>.npy (block-kept cell order of each chunk) and the model.
Usage: python an_msb.py"""
import os, sys, json, glob, time, pickle
ROOT = os.getcwd(); CODE = f"{ROOT}/research/reverse_engineering/btc5m-bot/code"; sys.path.insert(0, CODE)
sys.argv = [sys.argv[0], "four"]
import warnings; warnings.filterwarnings("ignore")
import numpy as np, pandas as pd, lightgbm as lgb
import train3 as t3
import blkaug9 as ba
from block_bins import block_seconds
from block_presence import keep_mask
from decision_presence import MKT_PURE

C = f"{ROOT}/.cache/re/btc5m-bot"; EX = f"{ROOT}/.cache/exam/btc5m-bot"; AN = f"{EX}/an"; CAP = f"{EX}/capture"
LOT = [(1792713600, 1792800000), (1792886400, 1792972800), (1793059200, 1793145600), (1793232000, 1793318400)]
FIT = [1792195200, 1792281600, 1792368000]
PMF = [f"pm_{side}_{q}_{j}" for side in ("o", "x") for q in ("n", "v") for j in range(5)] + ["pm_o_sell"]
COLS = MKT_PURE + ba.AUG + PMF
H = 1792713600


def cap_trades(t0_ms, t1_ms, tokens, excl):
    """capture trade rows of the given tokens, without the excluded (cluster) transactions; filtered per row group to bound memory."""
    parts = []
    for mp in glob.glob(f"{CAP}/polymarket_*_meta.pkl"):
        day = os.path.basename(mp)[len("polymarket") + 1:-9]
        M = pickle.load(open(mp, "rb"))
        for i, (has, mn, mx) in enumerate(M["stats"]["exchangeTimestampMs"]):
            if has and not (mx < t0_ms or mn > t1_ms):
                p = f"{CAP}/polymarket_{day}_rg{i}.parquet"
                if os.path.exists(p):
                    x = pd.read_parquet(p, columns=["exchangeTimestampMs", "transactionHash", "tokenId", "tradeSize", "tradeSide"])
                    keep = np.fromiter(((str(t) in tokens) and (str(h).lower() not in excl) for t, h in zip(x.tokenId, x.transactionHash)), bool, len(x))
                    x = x[keep].drop(columns=["transactionHash"])
                    parts.append(x)
    return pd.concat(parts, ignore_index=True) if parts else None


def pm_feats(c, tr, win_tok, excl):
    tau = ((c.start_ts.to_numpy(np.int64) + c.rel.to_numpy(np.int64)) * 1000)
    n = len(c); out = {k: np.zeros(n, np.float32) for k in PMF}
    tr = tr.assign(tokenId=lambda x: x.tokenId.astype(str)).sort_values("exchangeTimestampMs", kind="stable")
    bt = {k: (g.exchangeTimestampMs.to_numpy(np.int64), np.concatenate([[0.0], np.cumsum(g.tradeSize.to_numpy(float))])) for k, g in tr[tr.tradeSide == "BUY"].groupby("tokenId")}
    sl = {k: g.exchangeTimestampMs.to_numpy(np.int64) for k, g in tr[tr.tradeSide == "SELL"].groupby("tokenId")}
    keys = pd.DataFrame({"cid": c.cid.to_numpy(), "up": c.is_up.to_numpy(bool)}).groupby(["cid", "up"]).indices
    for (cc, uu), ii in keys.items():
        if cc not in win_tok:
            continue
        to, tx = (win_tok[cc][0], win_tok[cc][1]) if uu else (win_tok[cc][1], win_tok[cc][0])
        tt = tau[ii]
        for side, tk in (("o", to), ("x", tx)):
            if tk not in bt:
                continue
            T_, cs = bt[tk]
            for j in range(5):
                a = np.searchsorted(T_, tt - 3500 + 500 * j, "left"); b = np.searchsorted(T_, tt - 3000 + 500 * j, "left")
                out[f"pm_{side}_n_{j}"][ii] = b - a; out[f"pm_{side}_v_{j}"][ii] = cs[b] - cs[a]
        if to in sl:
            T_ = sl[to]; out["pm_o_sell"][ii] = np.searchsorted(T_, tt - 1000, "left") - np.searchsorted(T_, tt - 3500, "left")
    return out


def main():
    t0 = time.time(); rng = np.random.default_rng(14)
    mpath = f"{EX}/models/msb_refit.txt"
    need = sorted(set(MKT_PURE) | set(ba.OTH) | {"wi", "is_up", "rel", "start_ts", "cid", "y", "age_last", "ask_o", "m_last"})
    if not os.path.exists(mpath):
        fl = pd.read_parquet(f"{C}/fills.parquet", columns=["block", "ts", "tx"])
        bs = block_seconds(fl[fl.ts < H]); excl = set(fl.tx.str.lower())
        win = pd.read_parquet(f"{C}/windows.parquet", columns=["cid", "start_ts", "up_token", "down_token"])
        win_tok = {r.cid: (str(r.up_token), str(r.down_token)) for r in win.itertuples()}
        parts = []
        for d0 in FIT:
            c = ba.add_aug(pd.read_parquet(f"{C}/cells/{d0}.parquet", columns=need))
            t = (c.start_ts.to_numpy() + c.rel.to_numpy()).astype(np.int64)
            c = c[keep_mask(t, bs)].reset_index(drop=True)
            tk = set(str(t) for cc in c.cid.unique() if cc in win_tok for t in win_tok[cc])
            tr = cap_trades(d0 * 1000 - 10000, (d0 + 86400) * 1000 + 10000, tk, excl)
            ex = pm_feats(c, tr, win_tok, excl)
            for k, v in ex.items():
                c[k] = v
            sel = (c.y.to_numpy() == 1) | (rng.random(len(c)) < 0.3)
            sub = c.loc[sel, COLS + ["y"]].copy(); sub["w"] = np.where(sub.y == 1, 1.0, 1 / 0.3)
            parts.append(sub); del c, tr
            print("fit day", d0, round(time.time() - t0), flush=True)
        B = pd.concat(parts, ignore_index=True)
        m = lgb.train(t3.PARAMS, lgb.Dataset(B[COLS], B.y, weight=B.w), num_boost_round=200); m.save_model(mpath)
        imp = pd.Series(m.feature_importance("gain"), index=COLS)
        json.dump({"rows": int(len(B)), "capture_share_of_gain": round(float(imp[PMF].sum() / imp.sum()), 4)}, open(f"{EX}/models/msb_refit_info.json", "w"))
        del B
    m = lgb.Booster(model_file=mpath)
    for p in sorted(glob.glob(f"{EX}/chunks/*_*/evaluate.json")):
        d = os.path.dirname(p); a, b = map(int, os.path.basename(d).split("_"))
        if not any(x <= a < y for x, y in LOT):
            continue
        o = f"{AN}/msb_{a}_{b}.npy"
        if os.path.exists(o):
            continue
        c = pd.read_parquet(f"{d}/cells.parquet", columns=need)
        kb = np.load(f"{d}/block_keep.npy"); c["_row"] = np.arange(len(c))
        win = pd.read_parquet(f"{d}/windows_all.parquet"); win_tok = {r.cid: (str(r.up_token), str(r.down_token)) for r in win.itertuples()}
        excl = set(pd.read_parquet(f"{d}/fills.parquet", columns=["tx"]).tx.str.lower())
        c = ba.add_aug(c).sort_values("_row").reset_index(drop=True)
        c = c[kb].reset_index(drop=True)
        tk = set(str(t) for cc in c.cid.unique() if cc in win_tok for t in win_tok[cc])
        tr = cap_trades((a - 10) * 1000, (b + 310) * 1000, tk, excl)
        if tr is None:
            print("no capture", a, b); continue
        ex = pm_feats(c, tr, win_tok, excl)
        for k, v in ex.items():
            c[k] = v
        np.save(o, m.predict(c[COLS]).astype(np.float32))
        print("scored", a, b, len(c), round(time.time() - t0), flush=True)


if __name__ == "__main__":
    main()

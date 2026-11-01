"""Iteration 17 (X172 = mechanics panel P4): is the fast fan-out follower (< 150 ms after the previous operator order on the same window
and outcome) a SECOND decision fired by a later Binance tick, or one decision posted twice? Capture day 10-21 (local copy of the public
capture): Binance spot book microprice on Te = receive - 131 ms (the frozen clock). (a) PSTH of signed microprice changes toward o per
10-ms bin of (anchor - Te), anchor = the follower's match m_F or the leader's m_L, placebo anchor - 3 s subtracted; peak and half-max
width per alignment. (b) The 'gap band': the signed move in (m_L - 260, m_F - 260] (spot information the follower could have seen and
the leader could not); P(move > 0 toward o), against leaders without a follower given the same gap (drawn from the followers' gaps),
and its relation to the gap. Usage: python fol17.py"""
import os, sys, json
import numpy as np, pandas as pd, pyarrow.parquet as pq
S = os.environ["RE16_SCRATCH"]
_ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", ".."))
DAY = "2026-10-21"
p = pd.read_parquet(S + "/it14/dcfit14_pred.parquet", columns=["cid", "wallet", "up", "m", "start_ts"])
d0 = int(pd.Timestamp(DAY, tz="UTC").timestamp())
p = p[(p.start_ts >= d0) & (p.start_ts < d0 + 86400)].sort_values(["cid", "up", "m"]).reset_index(drop=True)
gap = p.m - p.groupby(["cid", "up"]).m.shift(); nxt = p.groupby(["cid", "up"]).m.shift(-1) - p.m
p["gap"] = gap; p["nxt"] = nxt
fol = p[p.gap < 150].copy(); fol["mL"] = fol.m - fol.gap
lead_single = p[(p.gap.isna() | (p.gap >= 400)) & (p.nxt.isna() | (p.nxt >= 400))].copy()
lo, hi = int(p.m.min()) - 5000, int(p.m.max()) + 1000
t = pq.read_table(f"{S}/it13/hf_dl/btc_{DAY}.parquet", columns=["type", "receivedTimestampMs", "bidPrice", "bidQuantity", "askPrice", "askQuantity"],
                  filters=[("type", "==", "book"), ("receivedTimestampMs", ">=", lo), ("receivedTimestampMs", "<", hi)])
Te = t.column("receivedTimestampMs").to_numpy().astype(np.int64) - 131
bp, bq, ap, aq = (t.column(k).to_numpy().astype(float) for k in ("bidPrice", "bidQuantity", "askPrice", "askQuantity"))
del t
mic = (bp * aq + ap * bq) / (bq + aq); del bp, bq, ap, aq
o = np.argsort(Te, kind="stable"); Te, mic = Te[o], mic[o]
dm = np.r_[0.0, np.diff(mic)]
BW, NB = 10, 60


def psth(anchors, sgn):
    H = np.zeros(NB); Hp = np.zeros(NB)
    for a_, s_ in zip(anchors, sgn):
        for sh, acc in ((0, H), (3000, Hp)):
            l, h = np.searchsorted(Te, a_ - sh - NB * BW, "left"), np.searchsorted(Te, a_ - sh, "right")
            if h > l:
                b = ((a_ - sh - Te[l:h]) // BW).astype(int); k = (b >= 0) & (b < NB)
                np.add.at(acc, b[k], s_ * dm[l:h][k])
    D = (H - Hp) / max(len(anchors), 1)
    pk = int(np.argmax(D)); above = np.where(D >= D[pk] / 2)[0]
    return {"peak_ms": pk * BW + 5, "peak": round(float(D[pk]), 5), "half_max_ms": [int(above.min() * BW), int(above.max() * BW + BW)], "D50": [round(float(D[i:i + 5].sum()), 4) for i in range(0, NB, 5)]}


sgnF = np.where(fol.up == 1, 1.0, -1.0)
res = {"day": DAY, "orders": int(len(p)), "fast_followers": int(len(fol)), "gap_q": [float(x) for x in fol.gap.quantile([0.1, 0.5, 0.9])]}
res["psth_follower_at_mF"] = psth(fol.m.to_numpy(np.int64), sgnF)
res["psth_follower_at_mL"] = psth(fol.mL.to_numpy(np.int64), sgnF)
res["psth_singles_at_m"] = psth(lead_single.m.to_numpy(np.int64), np.where(lead_single.up == 1, 1.0, -1.0))


def band_move(a_, b_, s_):
    x0 = np.interp(a_, Te, mic); x1 = np.interp(b_, Te, mic)
    i0 = np.searchsorted(Te, a_, "right") - 1; i1 = np.searchsorted(Te, b_, "right") - 1
    v0 = mic[np.clip(i0, 0, len(mic) - 1)]; v1 = mic[np.clip(i1, 0, len(mic) - 1)]
    return s_ * (v1 - v0)


mvF = band_move(fol.mL.to_numpy() - 260, fol.m.to_numpy() - 260, sgnF)
rng = np.random.default_rng(3)
gs = rng.choice(fol.gap.to_numpy(), len(lead_single))
sgS = np.where(lead_single.up == 1, 1.0, -1.0)
mvS = band_move(lead_single.m.to_numpy() - 260, lead_single.m.to_numpy() + gs - 260, sgS)
res["gap_band_move_toward_o"] = {"followers_P_pos": round(float((mvF > 0).mean()), 4), "followers_P_neg": round(float((mvF < 0).mean()), 4), "followers_P_zero": round(float((mvF == 0).mean()), 4),
                                 "singles_same_gaps_P_pos": round(float((mvS > 0).mean()), 4), "singles_P_neg": round(float((mvS < 0).mean()), 4), "singles_P_zero": round(float((mvS == 0).mean()), 4)}
fol["mv"] = mvF
res["followers_P_pos_by_gap"] = {str(k): round(float(v), 4) for k, v in fol.groupby(pd.cut(fol.gap, [-1, 10, 30, 60, 100, 150])).mv.apply(lambda s: (s > 0).mean()).items()}
json.dump(res, open(_ROOT + "/research/reverse_engineering/btc5m-bot/results/fol17.json", "w"), indent=1)
print(json.dumps(res, indent=1))

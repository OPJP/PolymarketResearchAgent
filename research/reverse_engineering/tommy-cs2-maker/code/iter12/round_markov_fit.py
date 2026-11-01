"""X171 (assumptions panel iter-11 P5) with X160's economy question: is the wallet's CS2 value V a round-score Markov
valuation between in-round events?

Clock-free hidden-Markov fit (pre-registered in NOTES iteration 12). Per map market (CS2 child_moneyline "Map k" of
16-22 Oct with a bo3 round sequence):
  * observations: the wallet's filled maker BUY orders grouped into bursts (same token, signed within 50 ms; level =
    the burst's highest price), in team-A space y = price (outcome 0) or 1 - price (outcome 1); band-edge levels
    (<= 0.06 or >= 0.94) dropped;
  * hidden state k = completed rounds (0..R), non-decreasing, at most floor(gap / 40 s) + 1 round ends between
    consecutive bursts, free start;
  * emission y ~ N(M_k(p) + mu_token, sigma^2), M = MR12 with MR3 overtime at a constant round-win probability p
    (grid), mu per token and sigma by two Viterbi-EM passes;
  * the true bo3 winner sequence against N_PERM permutations with the same final score (vectorised Viterbi);
  * control: the same fit on the last public print (wallet transactions excluded) in team-A space at the same times.
Development data only (orders signed before H; tapes clipped to H).
"""
from __future__ import annotations

import json
import re
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "iter2"))
from polyrea.adapters.http import shared_client  # noqa: E402
from common import H, OUT, RES, SPLIT, TAPES, WALLET  # noqa: E402
from pack_vs_rounds import bo3_maps, norm  # noqa: E402

N_PERM = 200
PGRID = np.round(np.arange(0.35, 0.651, 0.05), 3)
MIN_ROUND_GAP = 40.0
BURST_MS = 50.0


def markov_table(p: float, R_max: int = 60) -> np.ndarray:
    """M[a, b] = P(team A wins the map | score a-b), MR12 (first to 13) with MR3 overtime (first to 4 of 6, 3-3 repeats)."""
    q_ = 1 - p
    # overtime set value with O(3,3) = x: O(i,j) linear in x -> solve
    A = np.zeros((5, 5)); B = np.zeros((5, 5))  # O = A + B x
    for i in range(4, -1, -1):
        for j in range(4, -1, -1):
            if i == 4 and j < 4:
                A[i, j], B[i, j] = 1.0, 0.0
            elif j == 4 and i < 4:
                A[i, j], B[i, j] = 0.0, 0.0
            elif i == 4 and j == 4:
                continue
            elif i == 3 and j == 3:
                A[i, j], B[i, j] = 0.0, 1.0
            else:
                A[i, j] = p * A[i + 1, j] + q_ * A[i, j + 1]
                B[i, j] = p * B[i + 1, j] + q_ * B[i, j + 1]
    x = A[0, 0] / (1 - B[0, 0]) if B[0, 0] < 1 else 0.5
    O = A + B * x
    M = np.zeros((R_max + 1, R_max + 1))
    for a in range(R_max, -1, -1):
        for b in range(R_max, -1, -1):
            if a < 12 or b < 12:
                if a >= 13 and b < a and b <= 11:
                    M[a, b] = 1.0
                elif b >= 13 and a < b and a <= 11:
                    M[a, b] = 0.0
                elif a == 12 and b == 12:
                    M[a, b] = x
                elif a > 12 or b > 12:
                    M[a, b] = 1.0 if a > b else 0.0
                else:
                    M[a, b] = p * M[a + 1, b] + q_ * M[a, b + 1] if (a + 1 <= R_max and b + 1 <= R_max) else 0.5
            else:
                n = (min(a, b) - 12) // 3
                i, j = a - 12 - 3 * n, b - 12 - 3 * n
                if i >= 4 and j < 4:
                    M[a, b] = 1.0
                elif j >= 4 and i < 4:
                    M[a, b] = 0.0
                else:
                    M[a, b] = O[min(i, 4), min(j, 4)]
    return M


_TCACHE: dict = {}


def path_values(win: np.ndarray, p: float) -> np.ndarray:
    """win: (P, R) 1 if team A won round r. Returns (P, R+1) map-win probability after k rounds."""
    key = round(float(p), 4)
    if key not in _TCACHE:
        _TCACHE[key] = markov_table(p)
    M = _TCACHE[key]
    P, R = win.shape
    a = np.concatenate([np.zeros((P, 1), int), np.cumsum(win, axis=1)], axis=1)
    b = np.concatenate([np.zeros((P, 1), int), np.cumsum(1 - win, axis=1)], axis=1)
    a = np.minimum(a, M.shape[0] - 1); b = np.minimum(b, M.shape[1] - 1)
    return M[a, b]


def viterbi(y, tok, t, Mk, mu, sig):
    """Vectorised over P sequences. Mk (P, K), mu (P, 2), sig (P,). Returns path (P, N), loglik (P,)."""
    P, K = Mk.shape
    N = len(y)
    J = np.zeros(N, int)
    J[1:] = np.minimum(np.floor(np.diff(t) / MIN_ROUND_GAP).astype(int) + 1, K - 1)
    back = np.zeros((N, P, K), np.int16)

    def emis(i):
        r = (y[i] - Mk - mu[:, [tok[i]]]) / sig[:, None]
        return -0.5 * r * r - np.log(sig)[:, None]

    D = emis(0)
    for i in range(1, N):
        m = D.copy(); arg = np.zeros((P, K), np.int16)
        for j in range(1, J[i] + 1):
            cand = np.full((P, K), -np.inf); cand[:, j:] = D[:, :-j]
            better = cand > m
            m = np.where(better, cand, m); arg = np.where(better, j, arg)
        back[i] = arg
        D = m + emis(i)
    k = np.argmax(D, axis=1)
    ll = D[np.arange(P), k]
    path = np.zeros((P, N), int)
    path[:, -1] = k
    for i in range(N - 1, 0, -1):
        k = k - back[i][np.arange(P), k]
        path[:, i - 1] = k
    return path, ll


def fit(y, tok, t, win):
    """Best over the p grid of two Viterbi-EM passes; returns dict of arrays over P sequences."""
    P = win.shape[0]
    best = {"ll": np.full(P, -np.inf)}
    for p in PGRID:
        Mk = path_values(win, p)
        mu = np.tile(np.array([[-0.02, 0.02]]), (P, 1)); sig = np.full(P, 0.04)
        for _ in range(2):
            path, _ll = viterbi(y, tok, t, Mk, mu, sig)
            fitted = Mk[np.arange(P)[:, None], path]
            res = y[None, :] - fitted
            for s in (0, 1):
                msk = tok == s
                if msk.any():
                    mu[:, s] = res[:, msk].mean(axis=1)
            r2 = res - mu[:, tok]
            sig = np.maximum(r2.std(axis=1), 0.005)
        fitted = Mk[np.arange(P)[:, None], path]
        r2 = y[None, :] - fitted - mu[:, tok]
        ll = (-0.5 * (r2 / sig[:, None]) ** 2 - np.log(sig)[:, None]).sum(axis=1)
        upd = ll > best["ll"]
        if upd.any():
            for kname, val in (("ll", ll), ("sig", sig), ("p", np.full(P, p)), ("mu0", mu[:, 0]), ("mu1", mu[:, 1])):
                if kname not in best:
                    best[kname] = np.zeros(P)
                best[kname] = np.where(upd, val, best[kname])
            if "path" not in best:
                best["path"] = path.copy(); best["res"] = r2.copy()
            best["path"][upd] = path[upd]; best["res"][upd] = r2[upd]
    return best


def freeze_res(path_row, res_row):
    """Residuals of the first burst after each inferred round end (path increments)."""
    inc = np.where(np.diff(path_row) > 0)[0] + 1
    return res_row[inc]


def main():
    t0 = time.time()
    h = shared_client()
    slugs = bo3_maps(h)
    mk = json.load(open(OUT / "markets_dev.json"))
    o = pd.read_parquet(OUT / "orders.parquet", columns=["sign_ms", "price", "cid", "oi", "role"])
    o = o[(o.role == "maker") & (o.sign_ms / 1000 < H)]
    cd = pd.read_parquet(OUT / "calldata_all.parquet", columns=["tx", "maker"])
    bad = set(cd.loc[cd.maker == WALLET, "tx"])
    rng = np.random.default_rng(12)
    rows, freeze_rows, skipped = [], [], []
    for cid, x in mk.items():
        if x.get("sportsMarketType") != "child_moneyline" or not x.get("question", "").startswith("Counter-Strike"):
            continue
        mm = re.search(r"Map (\d)", x["question"])
        if not mm:
            continue
        mapno = int(mm.group(1))
        oo = o[o.cid == cid].sort_values("sign_ms")
        if len(oo) < 30:
            continue
        outs = json.loads(x["outcomes"]) if isinstance(x["outcomes"], str) else x["outcomes"]
        a, b = norm(outs[0])[:6], norm(outs[1])[:6]
        cand = [s for s in slugs if a in norm(s) and b in norm(s)]
        if not cand:
            continue
        g, _ = h.get_json(f"https://api.bo3.gg/api/v1/matches/{cand[0]}", {"with": "games"}, adapter="bo3gg.match", max_age=None)
        gm = [yy for yy in (g.get("games") or []) if yy.get("number") == mapno]
        if not gm:
            continue
        r, _ = h.get_json(f"https://api.bo3.gg/api/v1/games/{gm[0]['id']}/rounds", {}, adapter="bo3gg.rounds", max_age=None)
        rounds = r.get("game_rounds") if isinstance(r, dict) else None
        if not rounds or len(rounds) < 13:
            continue
        rounds = sorted(rounds, key=lambda z: z["round_number"])
        wn = [norm(z.get("winner_clan_name")) for z in rounds]
        fa, fb = norm(outs[0]), norm(outs[1])
        isa = np.array([(w[:6] == a) or (len(w) >= 3 and (w in fa or fa in w)) for w in wn])
        isb = np.array([(w[:6] == b) or (len(w) >= 3 and (w in fb or fb in w)) for w in wn])
        if (isa & isb).any() or (isa | isb).mean() < 0.95 or isa.sum() == 0 or isb.sum() == 0:
            skipped.append(cid)
            continue
        win = isa.astype(int)
        # bursts
        oo = oo.assign(tok=oo.oi.astype(int))
        oo = oo[(oo.price > 0.06) & (oo.price < 0.94)]
        if len(oo) < 30:
            continue
        oo = oo.sort_values(["tok", "sign_ms"])
        newb = (oo.tok.diff() != 0) | (oo.sign_ms.diff() > BURST_MS)
        oo["bid"] = newb.cumsum()
        bb = oo.groupby("bid").agg(sign_ms=("sign_ms", "min"), price=("price", "max"), tok=("tok", "first")).sort_values("sign_ms")
        y = np.where(bb.tok == 0, bb.price, 1 - bb.price).astype(float)
        tok = bb.tok.to_numpy(int)
        tt = (bb.sign_ms.to_numpy() / 1000.0)
        # control: last public print in A space at the same times
        tp = TAPES / f"{cid}_tkw.parquet"
        yp = None
        if tp.exists():
            d = pd.read_parquet(tp)
            d = d[(d.timestamp < H) & ~d.transactionHash.isin(bad)].sort_values("timestamp")
            if len(d) >= 20:
                ts = d.timestamp.to_numpy(float)
                pa = np.where(d.outcomeIndex.astype(int) == 0, d.price.astype(float), 1 - d.price.astype(float))
                j = np.searchsorted(ts, tt, side="right") - 1
                ok = j >= 0
                yp = np.where(ok, pa[np.maximum(j, 0)], np.nan)
        perms = [win] + [rng.permutation(win) for _ in range(N_PERM)]
        W = np.array(perms)
        fv = fit(y, tok, tt, W)
        rank_v = float((fv["ll"][1:] >= fv["ll"][0]).mean())
        fr_v = freeze_res(fv["path"][0], fv["res"][0])
        row = {"cid": cid, "map": mapno, "gs": x.get("gameStartTime"), "build": (pd.Timestamp(x.get("gameStartTime")).timestamp() < SPLIT),
               "rounds": len(win), "bursts": len(y), "rank_v": rank_v, "sig_v": float(fv["sig"][0]), "p_v": float(fv["p"][0]),
               "mu0_v": float(fv["mu0"][0]), "mu1_v": float(fv["mu1"][0]), "sig_v_perm_med": float(np.median(fv["sig"][1:])),
               "freeze_sd_v": float(np.std(fr_v)) if len(fr_v) > 2 else np.nan, "freeze_n_v": int(len(fr_v)),
               "within1c_v": float((np.abs(fv["res"][0]) <= 0.0101).mean()),
               "within1c_v_perm_med": float(np.median((np.abs(fv["res"][1:]) <= 0.0101).mean(axis=1)))}
        if yp is not None and np.isfinite(yp).sum() >= 30:
            okp = np.isfinite(yp)
            fp = fit(yp[okp], tok[okp] * 0, tt[okp], W)  # print: one offset (token-free)
            fr_p = freeze_res(fp["path"][0], fp["res"][0])
            row.update({"rank_p": float((fp["ll"][1:] >= fp["ll"][0]).mean()), "sig_p": float(fp["sig"][0]),
                        "sig_p_perm_med": float(np.median(fp["sig"][1:])), "freeze_sd_p": float(np.std(fr_p)) if len(fr_p) > 2 else np.nan,
                        "within1c_p": float((np.abs(fp["res"][0]) <= 0.0101).mean()), "n_p": int(okp.sum())})
        rows.append(row)
        for v in fr_v:
            freeze_rows.append({"cid": cid, "res": float(v)})
        print(f"{len(rows):3d} map {cid[:10]} R={len(win)} N={len(y)} rank_v={rank_v:.3f} sig_v={row['sig_v']:.4f} "
              f"perm={row['sig_v_perm_med']:.4f} sig_p={row.get('sig_p', np.nan):.4f} rank_p={row.get('rank_p', np.nan):.3f} "
              f"[{time.time() - t0:.0f}s]", flush=True)
    s = pd.DataFrame(rows)
    s.to_parquet(OUT / "round_markov_fit_maps.parquet", index=False)
    res = {"maps": int(len(s)), "n_perm": N_PERM, "maps_skipped_team_names": len(skipped)}
    for name, sub in (("all", s), ("build", s[s.build]), ("validate", s[~s.build])):
        if not len(sub):
            continue
        q = {"maps": int(len(sub)), "rank_v_median": float(sub.rank_v.median()), "share_maps_rank_v_le_0.01": float((sub.rank_v <= 0.01).mean()),
             "sig_v_median": float(sub.sig_v.median()), "sig_v_perm_median": float(sub.sig_v_perm_med.median()),
             "freeze_sd_v_median": float(sub.freeze_sd_v.median()), "within1c_v_median": float(sub.within1c_v.median()),
             "within1c_v_perm_median": float(sub.within1c_v_perm_med.median())}
        if "sig_p" in sub:
            sp = sub.dropna(subset=["sig_p"])
            q.update({"maps_with_print": int(len(sp)), "rank_p_median": float(sp.rank_p.median()),
                      "share_maps_rank_p_le_0.01": float((sp.rank_p <= 0.01).mean()), "sig_p_median": float(sp.sig_p.median()),
                      "sig_p_perm_median": float(sp.sig_p_perm_med.median()), "freeze_sd_p_median": float(sp.freeze_sd_p.median()),
                      "within1c_p_median": float(sp.within1c_p.median()),
                      "sig_v_minus_sig_p_median": float((sp.sig_v - sp.sig_p).median()),
                      "share_maps_sig_v_lt_sig_p": float((sp.sig_v < sp.sig_p).mean())})
        res[name] = q
    v = res.get("all", {})
    res["verdict"] = ("round-state V" if (v.get("rank_v_median", 1) <= 0.01 and v.get("sig_v_minus_sig_p_median", 0) <= -0.015
                                          and v.get("freeze_sd_v_median", 1) <= 0.03) else "not a score table (pre-registered rule)")
    json.dump(res, open(RES / "results/round_markov_fit.json", "w"), indent=1)
    print(json.dumps(res, indent=1))


if __name__ == "__main__":
    main()

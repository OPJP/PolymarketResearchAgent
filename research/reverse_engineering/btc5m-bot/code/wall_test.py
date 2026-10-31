"""Iteration 3: information-wall test. On VALIDATE one-sided seconds (val_side_it3.parquet: bot side, our best PIT side
model ps), compare how well the BOT's side and OUR PIT model's side predict FUTURE Binance futures moves (after the
bot's decision). If the bot's side predicts the future better than a model of all public PIT data, and still does so
conditional on our prediction, the bot uses information that is not in the public PIT data we have (or not archived).
Also: does the bot's side predict the future when futures AND spot were flat up to s (including the non-PIT [s-1, s))?"""
import os, sys, json
_ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", ".."))
import numpy as np, pandas as pd
import statsmodels.api as sm
C = _ROOT + "/.cache/re/btc5m-bot"; R = _ROOT + "/research/reverse_engineering/btc5m-bot"
V0, V1 = 1792108800, 1792713600
S = pd.read_parquet(f"{C}/{sys.argv[1] if len(sys.argv) > 1 else 'val_side_it3.parquet'}")
S["s"] = (S.start_ts + S.rel).astype(np.int64)
parts = []
for d0 in range(V0, V1, 86400):
    f = pd.read_parquet(f"{C}/fut/{d0}.parquet").sort_values("T", kind="stable")
    T = f["T"].to_numpy(np.int64); lp = np.log(f.p.to_numpy())
    g = S[(S.s >= d0 + 20) & (S.s < d0 + 86400 - 20)].copy()
    s = g.s.to_numpy(np.int64) * 1000
    px = lambda t: lp[np.clip(np.searchsorted(T, t, side="left") - 1, 0, None)]
    for nm, a, b in [("f_m1_0", -1000, 0), ("f_0_2", 0, 2000), ("f_2_5", 2000, 5000), ("f_5_15", 5000, 15000), ("f_0_15", 0, 15000), ("f_past_to_s", -4000, 0)]:
        g[nm] = (px(s + b) - px(s + a)) * 1e4
    parts.append(g)
D = pd.concat(parts, ignore_index=True)
bot = np.where(D.truth_up == 1, 1.0, -1.0); ours = np.where(D.ps >= 0.5, 1.0, -1.0)
res = {"n_seconds": int(len(D))}
def agree(side, col, mask):
    m = D[col].to_numpy(); k = mask & (np.abs(m) > 1e-9)
    return round(float((np.sign(m[k]) == side[k]).mean()), 4), int(k.sum())
allm = np.ones(len(D), bool)
flat_pit = (np.abs(D.F_pm3000u.to_numpy()) < 0.3) & (np.abs(D.r3.to_numpy()) < 0.01)
flat_s = flat_pit & (np.abs(D.f_past_to_s.to_numpy()) < 0.3)
for nm, mask in [("all", allm), ("flat_PIT_futures_and_spot", flat_pit), ("flat_futures_to_s_nonPIT", flat_s)]:
    r = {"share": round(float(mask.mean()), 4)}
    for col in ("f_m1_0", "f_0_2", "f_2_5", "f_5_15"):
        r[col] = {"bot": agree(bot, col, mask), "our_PIT_model": agree(ours, col, mask)}
    # conditional on our model: logit of sign(future 0-15 s move) on [bot side, our ps (centered)]
    m = D.f_0_15.to_numpy(); k = mask & (np.abs(m) > 1e-9)
    X = sm.add_constant(np.column_stack([bot[k], (D.ps.to_numpy()[k] - 0.5) * 2]))
    fit = sm.Logit((m[k] > 0).astype(float), X).fit(disp=0)
    r["logit_future_0_15_on_bot_side_and_our_score"] = {"coef_bot": round(float(fit.params[1]), 4), "z_bot": round(float(fit.tvalues[1]), 2),
                                                          "coef_ours": round(float(fit.params[2]), 4), "z_ours": round(float(fit.tvalues[2]), 2), "n": int(k.sum())}
    # within our-prediction groups: agreement of bot side with the future when bot disagrees with our model
    dis = k & (bot != ours)
    r["bot_disagrees_with_model:bot_agrees_future_0_15"] = (round(float((np.sign(m[dis]) == bot[dis]).mean()), 4), int(dis.sum()))
    res[nm] = r
json.dump(res, open(f"{R}/results_wall_test_iter3{'_' + sys.argv[1].split('.')[0] if len(sys.argv) > 1 else ''}.json", "w"), indent=1)
for k, v in res.items():
    print(k, v)

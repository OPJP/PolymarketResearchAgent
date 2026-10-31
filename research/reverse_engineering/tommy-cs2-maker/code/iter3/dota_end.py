"""Iteration 3, X24 retrospective: does the wallet see a Dota 2 map's decisive events before the market?

For each Dota 2 map market of the wallet (development units: 10-22 and the 10-31 12-18 block), the public taker tape
(data-api, block time) gives the market's settlement move: the first print at which the eventual winner trades at
>= 0.90 and never again below 0.80. OpenDota gives the game's start_time and duration (game seconds from the horn).
Reported per map: settlement time - start_time - duration (the market's end offset, which includes the draft, the
pre-game, pauses and the broadcast delay), and the wallet's last taker order and last maker signing on the map market
relative to the settlement move; plus its taker orders in the 120 s before the settlement move (and their team).
Output: results/dota_end.json
"""
import json
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from polyrea.adapters.http import shared_client  # noqa: E402
from polyrea.adapters.polymarket import PolymarketData  # noqa: E402
from server_clock import OUT, RES, WALLET  # noqa: E402
from dota_align import SERIES, norm  # noqa: E402


def main():
    h = shared_client()
    pm = PolymarketData()
    o = pd.read_parquet(OUT / "orders.parquet")
    d = pd.read_parquet(OUT / "calldata_dev.parquet")
    dm = pd.read_parquet(OUT / "dev_markets.parquet")
    hist = o[o.event.str.startswith("dota2")][["event", "cid", "token_id", "sign_ms", "role"]]
    dv = d[(d.maker == WALLET) & d.condition_id.isin(dm[dm.event.str.startswith("dota2")].cid)].copy()
    dv["role"] = np.where(dv.idx == -1, "taker", "maker")
    dv = dv.drop_duplicates(["salt", "sign_ms"]).assign(event=lambda x: x.condition_id.map(dict(zip(dm.cid, dm.event))), cid=lambda x: x.condition_id)
    W = pd.concat([hist, dv[["event", "cid", "token_id", "sign_ms", "role"]]])
    mk, _ = pm.markets_by_condition(sorted(W.cid.unique()))
    out = []
    for ev, mids in SERIES.items():
        for cid in W[W.event == ev].cid.unique():
            x = mk.get(cid) or {}
            mm = re.search(r"Game (\d)", x.get("question", ""))
            if not mm:
                continue
            n = int(mm.group(1))
            if n > len(mids):
                continue
            g, _ = h.get_json(f"https://api.opendota.com/api/matches/{mids[n - 1]}", {}, adapter="opendota.match", max_age=None)
            toks = json.loads(x["clobTokenIds"]) if isinstance(x.get("clobTokenIds"), str) else x.get("clobTokenIds")
            outs = json.loads(x["outcomes"]) if isinstance(x.get("outcomes"), str) else x.get("outcomes")
            rn = norm(g.get("radiant_name"))
            win = "r" if g.get("radiant_win") else "d"
            winner_idx = None
            for i, nm in enumerate(outs):
                side = "r" if norm(nm)[:5] in rn else "d"
                if side == win:
                    winner_idx = i
            gs = pd.Timestamp(x.get("gameStartTime").replace("+00", "+00:00")).timestamp() if x.get("gameStartTime") else g["start_time"] - 3600
            rows, _, _ = pm.market_trades(cid, start=int(g["start_time"]) - 600, end=int(g["start_time"] + g["duration"] + 3 * 3600), taker_only=True)
            tp = pd.DataFrame(rows)
            if tp.empty or winner_idx is None:
                continue
            tp = tp[tp.proxyWallet.str.lower() != WALLET].sort_values("timestamp")
            pw = np.where(tp.outcomeIndex.astype(int) == winner_idx, tp.price.astype(float), 1 - tp.price.astype(float))
            ts = tp.timestamp.to_numpy(float)
            settle = None
            for i in range(len(pw)):
                if pw[i] >= 0.90 and (pw[i:] >= 0.80).all():
                    settle = ts[i]
                    break
            if settle is None:
                continue
            w = W[W.cid == cid]
            wt = w[w.role == "taker"]
            win_tok = str(toks[winner_idx])
            pre = wt[(wt.sign_ms / 1000 >= settle - 120) & (wt.sign_ms / 1000 < settle)]
            out.append({"event": ev, "map": n, "market_end_offset_s": round(settle - g["start_time"] - g["duration"], 1),
                        "wallet_last_taker_minus_settle_s": round(float(wt.sign_ms.max() / 1000 - settle), 1) if len(wt) else None,
                        "wallet_last_maker_sign_minus_settle_s": round(float(w[w.role == "maker"].sign_ms.max() / 1000 - settle), 1) if (w.role == "maker").any() else None,
                        "wallet_takers_in_120s_before_settle": int(len(pre)),
                        "of_which_on_winner": int((pre.token_id.astype(str) == win_tok).sum()),
                        "takers_total": int(len(wt)), "duration_s": g["duration"]})
    json.dump(out, open(RES / "dota_end.json", "w"), indent=1)
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()

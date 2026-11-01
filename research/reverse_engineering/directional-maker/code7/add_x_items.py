"""Iteration 7: add the iteration-6 panel proposals to state.json as catalog items X43-X57 (status open)."""
import json
from pathlib import Path

P = Path(__file__).resolve().parents[1] / "state.json"
s = json.loads(P.read_text())
cat = s["catalog"]
new = {
    "X43": "panel iter6 information I1: score the Chainlink input on the historical lot via polymarket.com/api/crypto/crypto-price (settlement-grade 1-s series; reopens X42)",
    "X44": "panel iter6 information I2: streaming RTDS (filters \"\") with server publish ms; ms event study of the cluster's exact-500 re-posts around each publish (public-relay reader vs direct Data Streams); record through the sealed blocks",
    "X45": "panel iter6 information I3: taker trigger = the Polymarket page's Chainlink display (sell hazard after RTDS publishes vs futures moves; HFT vs non-HFT)",
    "X46": "panel iter6 information I4: the 10-30/10-31 change in Chainlink's 1-s stream (lag-1 autocorrelation) as a natural experiment; regime per block",
    "X47": "panel iter6 information I5: is the Chainlink skew the cluster's own reading or inherited from other makers' quotes (ms response of other makers' near-touch adds; book-state candidates in the center race)",
    "X48": "panel iter6 information I6: Kalshi KXBTC15M as the BTC 15m anchor (A4b)",
    "X49": "panel iter6 mechanics M1: every input on the engine's own clock (Chainlink stamp S used from ~S+0.7 s); phase-split agreement table per feed; latency-attributable part of each metric; nowcast",
    "X50": "panel iter6 mechanics M2: score the quote, not the fill: resting-at-touch presence label, Tobit of top-rung depth, single-join event model, two-stage fill presence",
    "X51": "panel iter6 mechanics M3: is the residual rung depth designed randomness (uniformity, independence, triplet identity, salt cycle) -> analytic presence ceiling",
    "X52": "panel iter6 mechanics M4: historical ms match clock from taker signatures and the ~190-ms taker speed bump; R4 price on the lot",
    "X53": "panel iter6 assumptions P1: decode the per-trade join decision as its own unit (post-trade touch vs Chainlink-skewed reservation price; threshold h_j; two-stage selection)",
    "X54": "panel iter6 assumptions P2: re-derive age/trigger/queue facts on resolved orders (remainder trail, salt clock)",
    "X55": "panel iter6 assumptions P3: prove the Chainlink gain against the strongest activity baseline (sub-second sequence and clean-book features)",
    "X56": "panel iter6 assumptions P4: locate the PnL by order type and by the source of the Chainlink-futures gap (noise vs lag)",
    "X57": "panel iter6 assumptions P5: US DST change on 11-01 as a natural experiment for the size session and the daily restart",
}
for k, v in new.items():
    if k not in cat:
        cat[k] = {"status": "open", "evidence": "source: " + v + ". Not done yet."}
P.write_text(json.dumps(s, indent=1))
print(len(cat), [k for k, v in cat.items() if v["status"] == "open"])

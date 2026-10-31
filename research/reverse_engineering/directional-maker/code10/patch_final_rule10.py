"""Iteration 10: update FINAL_RULE.md (R6 unchanged; components, economics, open leads)."""
from pathlib import Path

p = Path(__file__).resolve().parents[1] / "FINAL_RULE.md"
s = p.read_text(encoding="utf-8")
s = s.replace("# directional-maker: frozen rule R6 (iteration 8, kept unchanged in iteration 9)",
              "# directional-maker: frozen rule R6 (iteration 8, kept unchanged in iterations 9 and 10)")
a = s.index("| Side |")
b = s.index("| Price |")
new_side = (
    "| Side | **On the 10-31 12-18 development block it buys the outcome whose Chainlink edge over the Polymarket mid is positive** "
    "(Up iff the digital fair of Up from the report stamped floor((T - 1.432 s)/1 s), Gamma strike, 1.4 x 300-s realised vol, exceeds "
    "the Up mid of the latest book record; no fitted parameter): 0.786 per fill (n 2,244), 0.965 where the reference and the market "
    "disagree on the favourite (match ms and book mid, 14:06-16:30; 0.855 over 12-18 with the R6 inputs), 0.762 where they agree. "
    "**Iteration 10 (A1): this is not a stable rule of the engine's history.** With pre-registered historical proxies (match clock = "
    "taker signing ms + 620 ms clipped to [block - 3 s, block - 1.5 s], the real Chainlink value from the crypto-price endpoint, the "
    "last clean print at block - 3 s) that reproduce the 10-31 truth (0.953 vs 0.965), the lot's disagreement fills land on the "
    "Chainlink side only 0.657 (STUDY, n 108) / 0.680 (VALIDATE aggregate, n 153), schedule-size rungs only 0.667 / 0.697, and not "
    "more when the disagreement is large; 10-31 00-06 gives 0.679 (n 109; hour 00 UTC 0.24, hours 02-05 0.88-0.93). Imbalance pairing "
    "bids (11-14% of lot fills) sit on the under-held outcome 100% (own state). Off-posture fills are not lost cancel races (posture "
    "at the taker's arrival 0.70-0.72 vs 0.74 at the match). Per wallet 0.79 / 0.81 / 0.76 live: mo-money's 500 rungs are off the "
    "posture already when posted (0.646 at the add; the TWAP-60 topic gives 0.608). A per-phase fair (slow sigma / TWAP lock-in) "
    "scores 0.835 vs 0.813 on 15-18 but is mostly the slow sigma, which fails its historical replications: secondary only. "
    "Market-only baselines <= 0.63. | VALIDATE-only (live 10-31); fails the historical replication on the lot (A1) | "
    "`code8/fill_side.py`, `code9/vol_*.py`, `code10/a1_*.py`, `code10/m2_phase.py` |\n")
s = s[:a] + new_side + s[b:]
s = s.replace(
    "| Size | October: 500 x 2^k with a one-fifth level; 500 in the weekday 12-21 UTC session or when the 300-s futures vol at the open is high, else 62 / 250; June: 50 / 100 / 300; remainders re-posted. | VALIDATE-only | `code6/m5_size.py`, June calldata |",
    "| Size | October: schedule rungs 500 x 2^k with a one-fifth level (100 / 12 only at 30-120 s left); 500 in the weekday 12-21 UTC "
    "session or when the 300-s futures vol at the open is high, else 62 / 250; plus **imbalance pairing bids** of exactly the own "
    "|Up - Down| shares (calldata original size within 2% of the imbalance; 11-14% of lot fills; not remainders). July (pmxt pilot, "
    "same engine family): 500 / 300 / 50 + pairing sizes; June: 50 / 100 / 300. | VALIDATE-only | `code6/m5_size.py`, "
    "`code10/m1_pair_lot.py`, `code10/pmxt_pilot.py` |")
s = s.replace(
    "| Exit | Holds to resolution; small complement taker buys sized to the imbalance and merges (2-4% of PnL). | VALIDATE-only | `results/iter5_flatten.json` |",
    "| Exit | Holds to resolution; completes pairs with maker pairing bids on the under-held outcome, priced at the market rather than "
    "off its own cost (pair cost median 0.91 STUDY / 0.81 VALIDATE, below 1 in only 61-72%), plus small complement taker buys; merges "
    "~65 s before the end. Window PnL split (locked pairs vs directional residual): STUDY -$0.9k / +$5.7k, VALIDATE aggregate +$33.3k / "
    "-$10.3k: neither part is reliably the profit; the residual carries 58-69% of the window-to-window variance. | VALIDATE-only | "
    "`results/iter5_flatten.json`, `code10/m1_pair_lot.py` |")
s = s.replace(
    "matched ~0.7 s later; it stops ~30 s before the end. | VALIDATE-only (live) |",
    "matched ~0.7 s later; it stops ~30 s before the end; its filled rungs agree with the report in force at the match, not at the "
    "taker's signing (M5). July engine (pmxt): posts a median 69 ms after the market's previous trade, filled orders ~1.0 s old, 49% "
    "at the touch. | VALIDATE-only (live) |")
ws = s.index("## Why it works")
we = s.index("## Can a normal user deploy it now")
why = """## Why it works

It is a two-sided liquidity provider whose ladders hang off each market's Polymarket mid and are skewed toward the
settlement source, the Chainlink BTC/USD report, re-priced the moment Polymarket's public relay publishes each report. It
completes pairs: every own fill that leaves a window unbalanced is followed by a maker bid for exactly the missing shares on
the other outcome. Its BTC 5m fills earn 2-4% of volume (BUILD +2.2% on $1.6M, VALIDATE +4.3%); maker and taker rebates and
rewards add about a fifth of net PnL ($23.0k of $111.7k over 10-08..30, measured by the assumptions panel; BUILD maker
rebates $14.5k against BTC 5m's $35k), and BTC 15m is near break-even before rebates (0.4% on $1.26M). Iteration 10 shows
that the profit cannot be pinned to one decision: the locked pairs earn -$0.9k on STUDY but +$33.3k on VALIDATE, the
directional residual +$5.7k vs -$10.3k. Who pays: takers who buy favourites through complement mints (88% of VALIDATE fills
are mints) fill its underdog bids, and in the 10-31 noise regime takers fill its Chainlink-skewed bids. The Chainlink skew
earned on the lot where the report and the market disagreed (+12.8% on those VALIDATE fills, block clock), but the strong
form seen on 10-31 is not the engine's stable behaviour (A1), and in the noise regime of 10-31 the BTC 5m blocks lost 11.9%
and 3.9% before BTC 5m was switched off.

"""
s = s[:ws] + why + s[we:]
s = s.replace("(~$45-56k of collateral per wallet)",
              "(a working capital of ~$22-24k per wallet, reset by a weekly Monday sweep at the 01:00 UTC restart and growing to "
              "$43-49k by the end of the week; no deposits in 10-09..30)")
ol = s.index("## Open leads")
s = s[:ol] + """## Open leads (not part of the frozen rule)

- A1 follow-up: what sets the side on the lot where Chainlink and the market disagree (0.66-0.70 on the Chainlink side;
  neither Binance nor the market favourite explains it); a per-window regime test against the Chainlink 1-s noise (noise
  runs for every hour of 10-31 00-06 and the lot's fill stamps are being fetched by a detached job to 11-01 10:00 UTC).
- Slow vs fast volatility and the per-phase fair: pre-registered for 11-01 06-12 and the 11-02 12-18 regime change.
- The quote unit as the primary unit for the next exam: examinable for BTC 5m/15m from the own exam recorder dx_clob
  (recall 1.00 vs the raw label) to 11-03 00:00 UTC, and for the other 5m/15m crypto families from the new dw_clob
  recorder (from 10-31 22:59 UTC); the shared recorder cannot label it (recall 0.01-0.02).
- The pmxt archive (07-16..08-10, unaggregated book with server ms and tx hashes for every family): the same engine
  family with another configuration, for the ladder state machine, the queue and the strict-fill replay (X64).
- Clock conventions across the US DST change (pre-registered, X99); module switches against public data-quality triggers
  (pre-registered, X89).
- Mo-money's 500-rung input (X91 / X94): neither a Chainlink delay, a Binance blend nor the TWAP-60 topic.
"""
p.write_text(s, encoding="utf-8")
print("ok", len(s))

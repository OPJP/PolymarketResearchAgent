"""Iteration-15 edit of FINAL_RULE.md (v6 title, intro bullet, iteration-15 section, outcome row, exit-cap note, target
metric rows, short notes in the mechanism / deployment / unexplained sections). Run once."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[5]
p = ROOT / "research/reverse_engineering/tommy-cs2-maker/FINAL_RULE.md"
s = p.read_text(encoding="utf-8")


def rep(old, new):
    global s
    assert old in s, old[:80]
    s = s.replace(old, new, 1)


rep("# tommy-cs2-maker: frozen rule v5 (`tommy-v5-grid-league-dota-groupP`; v4 plus group-P coverage in the selection score, iteration 9, 2026-11-01)",
    "# tommy-cs2-maker: frozen rule v6 (`tommy-v6-groupP-bidside-outcome`; v5 with a bid-side anchored outcome replay, iteration 15, 2026-11-01)")
rep("""  value's path on the feed's own clock, and the operator's sports quoting and further accounts.
""", """  value's path on the feed's own clock, and the operator's sports quoting and further accounts.
- Iteration 15 changed only the outcome component (v6): the executable replay in `evaluate()` now quotes one BUY level
  per token at the others' bid on that token (the latest wallet-free print that consumed bids on it, usable 2 s after
  its block) under a 0.99 pair cap, instead of anchoring both tokens on the last print. Selection, presence, price and
  size are v5's. It also re-decided which accounts are the operator's, tested the wallet's exit policy as the outcome
  carrier, and found the first evidence that the private value prices in-round events rather than round results only.
""")
SEC = """## What iteration 15 established (v6: the outcome replay; nothing else changed)

- **Outcome component replaced** (VALIDATE-only). `_replay_v6`: one level per token at floor(others' bid on that
  token), pair cap 0.99, band [0.05, 0.95], 100 shares (10 in Dota) refilled every 10 s, strict trade-through fills on the
  data-api taker tape. It was the BUILD choice among the pre-registered tape-engine variants and beat the frozen replay
  on VALIDATE in both coefficients: per-market Pearson / Spearman **0.197 / 0.027** (v5 replay -0.131 / -0.081; prints
  baseline 0.329 / 0.289). The gain removes the old replay's ask-side quotes; it is not a decode of the outcome.
- **The wallet's own exit policy does not carry the outcome** (X218). A five-slot public ladder with the measured net
  cap (about 600 CS2 shares) and the 200-600 taper, in the validated calldata engine: BUILD chooses no cap (0.067 /
  0.275), so VALIDATE stays at 0.315 / 0.238; capped variants reach 0.41-0.48 Pearson on VALIDATE but 0.11-0.21
  Spearman and negative BUILD Pearson.
- **Which accounts are the operator's.** Cross-market 0-5 ms co-signing with the wallet (the one-process test) confirms
  0x7d67f01d (4.4x) and refutes 0xd2bb9459, 0x10d79cc7, 0x68915897 and 0x5d40576b (0-1 pairs). Their earlier
  same-market co-signing is what co-subscribers of one feed produce. No attributed account quotes GRID events, so
  "never GRID" stays the operator's boundary. In 16-22 Oct 20 of 97 non-GRID operator events went to 0x7d67f01d only;
  that routing is too sparse to fit.
- **R vs K** (hypothesis). On the print-anchored round clock, the share of its value's move before the print's jump is
  the same in decided-early rounds (defuse after a wipe, bomb with CTs saving) as in elimination rounds (0.682 vs
  0.680; R predicted 0.40 or less). In save rounds it moves before any round-end message exists. So the feed's messages
  carry in-round state (kills, plant, alive counts), which fits PandaScore's Low Latency Feed (a token is needed to test).
- **Latency yardstick.** Its message-locked re-pricings come a median 1.1 s after the first visible co-receiver's take;
  a source arriving 0.25 s after the message would precede 85% of them.
- **New reported metric.** `price_within_tick_at_fill_m1c` = 0.496 on VALIDATE (the fill unit, last wallet-free print
  before the fill block minus 1c); the target metric stays the order unit at signing (0.322). Generic makers reach
  0.605 at the fill.

"""
rep("## What iteration 14 established (no rule change)", SEC + "## What iteration 14 established (no rule change)")
ROW = ("| Outcome (executable, v6) | `_replay_v6`: one BUY level per token at floor(others' bid on that token) = the latest wallet-free "
       "taker print that consumed bids on the token, usable 2 s after its block; pair cap 0.99; band [0.05, 0.95]; 100 shares "
       "(Dota 10) refilled every 10 s; strict trade-through fills; settlement PnL per market of v5-selected events. | VALIDATE-only "
       "| Per-market Pearson / Spearman with the wallet 0.197 / 0.027 (v5 replay -0.131 / -0.081; prints baseline 0.329 / 0.289; "
       "partial given prints 0.176). Not the wallet's process: its outcome needs its value and its informed takes (an oracle copy at "
       "2 s caps at 0.43 / 0.40; the wallet's exit policy in a public ladder does not lift it, X218). |\n")
rep("| Exit | Never sells.", ROW + "| Exit | Never sells.")
tail = "the band does not repair public replays (D 0.245 / 0.087 with it, 0.245 / 0.089 without). |"
rep(tail, tail[:-2] + " Iteration 15: net position capped near 600 CS2 shares with a long-side taper from 200 (share of fills on the long side 0.44 below 200, 0.21 at 400-600, 0.00-0.03 above 600). |")
rep("| `pnl_corr_pearson` / `pnl_corr_spearman` | -0.131 / -0.081 | Generic tape ladder on v5's selected events.",
    "| `pnl_corr_pearson` / `pnl_corr_spearman` | 0.197 / 0.027 (v6) | v6 bid-side anchored replay; the v5 generic tape ladder scored -0.131 / -0.081 on v5's selected events.")
rep("## Target metrics on VALIDATE (`state.json` `target_metrics`; v5, build constants)",
    "## Target metrics on VALIDATE (`state.json` `target_metrics`; v6, build constants)")
rep("| `price_within_tick` | 0.322 | In-play tick, last-print anchor.",
    "| `price_within_tick` | 0.322 | In-play tick, last-print anchor at signing (order unit). Fill unit (iteration 15, reported, not the target unit): 0.496 against the last print before the fill minus 1c; generic makers 0.605.")
rep("## Why it works (economic mechanism)\n", "## Why it works (economic mechanism)\n\n- **Iteration 15 note** (hypothesis). The private input carries "
    "in-round state, not only round results (decided-early rounds show no delay of its value). The operator is paid for reading "
    "kills, plants and alive counts from a push feed a second or more before the market prices them. Its counterparties are the "
    "makers it picks off and the takers who sell into its bids after it has already moved.\n")
rep("## Can a normal user deploy it now\n", "## Can a normal user deploy it now\n\n- **Iteration 15 note.** The feed has to deliver its messages "
    "within about 0.25 s of the first co-receiver to precede 85% of the wallet's message-locked re-pricings. Polymarket's sports "
    "socket polls round scores every 20.2 s and only for GRID events, and Valve's Dota snapshots arrive every 4 s, so neither can "
    "stand in for it. A public-only copy of the ladder (v6's outcome replay) earns about zero and does not track the wallet's "
    "per-market PnL.\n")
rep("## Not explained yet\n", "## Not explained yet\n\n- **Iteration 15 account.** Price: V at the message, now with evidence that the "
    "messages carry in-round state (K over R, hypothesis-level, weak clocks). Outcome: 0.197 / 0.027 for the frozen executable "
    "replay, 0.315 / 0.238 for the best public replay in the calldata engine; the wallet's exit policy does not change that. "
    "Selection: explained on VALIDATE; a small, drifting share of the operator's non-GRID events goes to 0x7d67f01d, which no "
    "listing field predicts out of fold with 20 cases.\n")
p.write_text(s, encoding="utf-8")
print("ok", len(s))

# dbdd-inplay-taker: lab notebook

Wallet `0xdbdd45150249e229eb4ca8aa48a30dca21faa5de` (in-play multi-sport taker).
Brief: `research/reverse_engineering/BRIEF.md`. Workspace: this folder + `.cache/re/dbdd-inplay-taker/`.

## Pre-registration (iteration 1, fixed for all iterations)

- H = 1792713600 (2026-10-23 00:00 UTC). Nothing at or after H is loaded (all fetches use `end < H`, tapes truncated at H).
- Unit of a market's period = its Gamma `gameStartTime` (fallback: the wallet's first fill in it).
- **BUILD** = markets with game start in [2026-09-23, 2026-10-13) = [1790121600, 1791849600) for tape-level work
  (plus the wallet's full own history before 2026-10-13 for descriptive work).
- **VALIDATE** = markets with game start in [2026-10-13, 2026-10-23) = [1791849600, 1792713600), tapes cut at H.
  Choices between candidate rules are made on VALIDATE only.
- **Primary metric (higher is better)**: `sel_auc` = within-market selection AUC on VALIDATE. Population: every
  taker BUY print (one data-api takerOnly row = one aggressive order) at or after game start in the VALIDATE
  markets the wallet traded. Positive = the wallet's prints. Score = the frozen rule's point-in-time score
  (features use only tape prints strictly before the print's own second, metadata known at listing, public
  feeds with >= 5 s delay). Pairs are formed only within the same market (pooled Mann-Whitney), so market choice
  cannot inflate it. No own-state features in the primary number.
- Secondary (always reported): recall and lift at the pre-registered threshold (top 20% of scores within the
  market population), permutation p (within-market label permutation), presence AUC on (market, 10 s bin),
  side accuracy vs market-only baseline (buy the favourite / buy the side whose price rose), price within one
  tick, per-market PnL correlation, rule return under strict fills (latency >= 2 s).

## Data gathered

(see sections below; updated as fetches complete)

## Hypotheses ledger

(see state.json for the machine-readable copy)

## Log

### Iteration 1 (2026-10-31, start 07:24 UTC)

**Data gathered (all < H)**
- Full wallet activity 2025-11-12 .. 2026-10-22: 509,053 rows (375,942 TRADE fills, 128,522 REDEEM, 4,446 MERGE,
  143 TAKER_REBATE) via 1,023 cursor pages -> `.cache/re/dbdd-inplay-taker/activity.parquet`.
- Gamma metadata for all 14,020 markets traded since 2026-09-21 -> `gamma.json` (slimmed).
- Full public taker tapes (data-api takerOnly) for EVERY market the wallet traded with game start in
  [2026-09-23, H): 13,262 markets (two workers, newest-first + BUILD oldest-first) -> `tapes/chunk*_*.parquet`.
  The earlier study used ~400 sampled markets from 30 days; this is ~33x more, and complete (not sampled).
- ESPN soccer keyEvents (goals, cards, subs, period marks, wall clocks) for soccer games the wallet traded in the
  window: 941 games attempted, 500 matched, 13,363 key events -> `espn_soccer_keyevents.parquet`.

**Whole-history description** (`describe_wallet.json`)
- 375,940 BUY vs 2 SELL fills, $28.06M, 124,058 markets in 11 months. One fill per transaction (activity rows),
  only 2.7% of seconds with fills hit more than one market (2.0% more than one event): it does NOT sweep many
  markets at the same second.
- Median fill $8.9 (10% below $1.0, 1% above $1,227); 45% of fills are integer share counts.
- Fills per market: median 2, p90 7. Gap between successive fills in a market: p10 14 s, median 158 s.
- 23.6% of markets have both tokens bought (it switches sides within a game).
- Volume peaked Mar-Apr 2026 ($4.3-4.6M/month); Oct 2026 (to the 22nd) $1.28M.
- Families by USD (all history): soccer/other $7.5M, CS2 $5.6M, ATP $1.8M, NBA $1.8M, ITF $1.7M, LoL $1.6M,
  MLB $1.4M, CBB $1.2M, Dota $0.85M, WTA $0.7M, Valorant $0.7M, NHL $0.55M.

**Tape window own-fill PnL** (`own_fills_window.json`; fee note: data-api `usdcSize` already INCLUDES the taker fee,
usdcSize/(size*price) = 1.024 on average, so PnL = size*payout - usdcSize)
- BUILD: 21,548 fills, $1.29M, PnL +$24.0k (+1.9%); VALIDATE: 10,963 fills, $0.61M, +$7.9k (+1.3%).
- By sport: soccer +6.6% ($419k), other (cricket, basketball ex-US, etc.) +9.0%, tennis +1.9% ($423k),
  US leagues -2.1% ($354k), esports -4.4% ($450k).
- Soccer profit is NOT mainly totals in this window: soccer moneyline +7.5% (buys favourites, avg px 0.59,
  wins 63%), team totals +36%, first-half totals +19%, spreads +21%, corners +24%; full-game totals -2.2%
  with only 42% Over. So "Over after a goal" is one slice, not the engine.

**First tape results (partial BUILD: 800 oldest BUILD markets; exploration on BUILD only)**
- Markout (`markout_result_BUILD.json`, descriptive, uses future prints): the bought token's last price moves in
  the wallet's favour after its prints: +0.18c at 5 s, +0.58c at 30 s, +1.36c at 2 min, +1.92c at 10 min,
  +1.46c to resolution; other takers in the same markets: +0.03c, +0.08c, +0.27c, +0.37c, +0.85c. The wallet is an
  INFORMED taker on a minutes horizon (5-7x others), and its 10-min markout exceeds its resolution markout: it
  captures information that the market prices within minutes.
- Pre-trade state (BUILD): median seconds since the previous print 18 s (others 5 s); quiet >= 10 s 65% (37%).
  Its token rose over the last 10 s in 59.5% of non-zero cases (others 53%), 30 s 58% (53%), but over 15 min only
  46% (52%). Signed taker flow toward its token in the last 60 s positive in 71% (59%). Favourite share 52% (55%).
  Reading: it buys after a recent up-tick / buying burst on its token once the book has gone quiet, often after
  a longer decline: residual mispriced asks after a fair-value jump that others started to price.
- Soccer vs ESPN goals (BUILD so far: only 13 games / 74 wallet prints - too small, re-run on full data):
  20% of wallet prints within 60 s after a goal wall clock (others 6%) and 15% within 60 s BEFORE one (others 7%).
- Explicit tape rules (`explicit_rules_result.json`): within-market AUC 0.52-0.58 BUILD, 0.53-0.56 VALIDATE.
- LightGBM on public tape + sibling features (partial data): VALIDATE within-market AUC 0.651, recall 31% at lift
  2.0 (top 15%); with the print's own size as a fingerprint 0.686. Top single features (BUILD): game minute and
  prints-so-far (the wallet trades EARLIER in a market's in-play life than other takers: AUC 0.39 => 0.61 reversed),
  recent volume (lower), quiet (higher), sibling 2-min move (higher).

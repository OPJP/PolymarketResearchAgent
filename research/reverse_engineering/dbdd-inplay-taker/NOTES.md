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
- Co-trader cluster (`leaders.py`, partial BUILD for selection): 21 wallets whose same-token buys are followed by
  ours within (2, 60] s at >= 5x a 15-min time-shift null (e.g. 0x21ce81f5: 170 vs 5; 0x93ef3fca: 119 vs 7;
  0x870a742f: 114 vs 8; 0x580325ef: 74 vs 4). Order is mixed: for 0x21ce/0x93ef/0xe37f the OTHER wallet more
  often buys after ours (396 vs 244, 291 vs 161, 283 vs 82); for 0x904e/0x54ac ours comes after (110 vs 44,
  79 vs 34). Reading: a cluster of bots acting on the SAME external signal within a minute, not a copier.
  As a public feature ("a cluster member other than the printer bought this token in [T-60, T-2]"):
  VALIDATE wallet 18.5% vs others 8.1% (2.3x); AUC 0.62 alone.

**Full-data results (all 13,262 markets; features 2.58M in-play taker BUY prints; wallet 32,297 prints;
BUILD 8,455 markets / 21,383 wallet prints; VALIDATE 4,759 markets / 10,914 wallet prints)**
- PRIMARY (pre-registered) `sel_auc` on VALIDATE, rule R-LGB-PUB-1 (LightGBM, public features, no own-state,
  no own size): **0.731**; recall 40.4% at lift 2.64 (top 15% within market), precision 3.5% vs base 1.34%,
  stratified rank-sum p ~ 0. The same model on the partial BUILD (800 markets) had 0.651: more data helped a lot.
  Gain importance: prints-so-far in the market (n_before) >> price, 5-min USD volume, print price minus last
  price, family, game minute, market type, quiet, 15-min and 5-min token moves.
- Diagnostic with the print's own size (fingerprint, not a strategy feature): 0.790, recall 48.5% at lift 3.17.
- Single-feature within-market AUCs on full BUILD are all weak (0.45-0.54): the signal is in interactions
  (market type x price x timing), not in one variable.
- Frozen-rule smoke test (`final_rule.metrics` on 300 random VALIDATE markets from cached features): AUC 0.711,
  recall 37.7% at lift 2.46; buying other takers' flagged prints (<= $10 each, fee included) returned +4.3%
  on $54.7k vs the wallet's +1.4% in those markets; per-market PnL correlation only 0.14.
- Soccer vs ESPN goal wall clocks (full BUILD: 343 games, 1,829 wallet prints, 164k other prints):
  within 60 s AFTER a goal: wallet 19.6% vs others 8.4% (2.3x); within 60 s BEFORE: 7.9% vs 5.8% (the pre-goal
  excess seen on 74 prints was noise). Wallet's reaction profile after the wall clock: 0-5 s 1.6%, 5-10 s 2.5%,
  10-20 s 4.2%, 20-30 s 3.5%, 30-45 s 4.1%, 45-60 s 3.4% (others 1.3, 0.9, 1.3, 1.1, 1.8, 1.8%): excess starts at
  5-10 s and peaks 10-30 s after the wall clock (3x), i.e. consistent with a feed about as fast as ESPN's
  wall clock + 10 s, not a sub-5 s courtside feed. By market type (share of wallet prints within 60 s after a
  goal vs others): moneyline 31% vs 10%, BTTS 32% vs 8%, halftime result 28% vs 5%, spreads 23% vs 7%,
  totals 19.5% vs 6.9% (88% Over), team totals 16.5% vs 5.8%; corners 1.7% vs 2.1% (no reaction, as expected).
  So goal reactions are ~20-30% of its soccer trades across ALL goal-sensitive markets, not only Over.

**Mechanism picture after iteration 1 (hypotheses, ranked)**
1. (supported) An informed in-play taker driven by an external fair value: its buys lead the Polymarket price by
   minutes (markout +1.4c at 2 min, +1.9c at 10 min vs +0.3/+0.4c for others), it trades into quiet books
   (median 18 s since the previous print vs 5 s), right after a short up-tick / buying burst on the token.
2. (supported, partial) Score-feed reaction: in soccer ~20% of its prints (31% in moneyline, 32% BTTS, 28%
   halftime result, 23% spreads, 19.5% totals) fall 0-60 s after an ESPN goal wall clock (2.3-5x others),
   with the excess starting 5-10 s and peaking 10-30 s after the wall clock: a feed about ESPN-speed + 10 s.
3. (supported) It is one of a cluster of bots acting on the same signal: >= 21 public wallets buy the same token
   within 60 s of it far above chance, in both orders. Their prints are public: a usable signal.
4. (open) What triggers the other ~75% of soccer trades and its tennis/esports trades (no public point/round
   feed tested yet); whether its fair value is a sharp bookmaker line (Pinnacle/Betfair-type, not public).

**Next iteration (priority order)**
- Add the cluster features (leader60, leader_since, number of distinct cluster wallets in 60 s) and ESPN goal
  features (seconds since last goal with D >= 5 s, goal-sensitive market flag) to the LightGBM; refit on BUILD,
  score VALIDATE. Expect the largest gain from the cluster feature (2.3x enrichment, mostly independent of tape).
- Run `presence.py` (written, not run) for presence AUC on (market, 10 s bin); build the side model (which token,
  vs favourite 52.8% baseline) and the price-within-one-tick metric.
- Esports/tennis event feeds: test bo3.gg / HLTV / Liquipedia round or map timestamps for CS2/Dota; tennis
  point-by-point sources. Lead-lag vs the cluster's first print to look for an information wall.
- On-chain OrderFilled for its taker fills: how many maker orders each fill consumes, whether it empties the
  best level (size = depth?), and its limit price vs fill price (sizing rule).
- Market selection: Gamma universe of in-play markets per day to learn which live markets it skips.
- Rule PnL on full VALIDATE with per-event bootstrap (smoke test: +4.3% on flagged other-taker prints).

**polyrea notes**: no bug found. Caveat for users: data-api `usdcSize` includes the taker fee (ratio 1.024 to
size*price here), so subtracting a modelled fee again double-counts it.
- NOTE: `leaders.py` on the full data exceeded the 3 GB RSS limit (3.8 GB: full tapes with string wallet/asset
  columns + merge) and was stopped; the cluster numbers above come from the earlier run (leaders selected on the
  first 800 BUILD markets, evaluated on the first 2,194 VALIDATE markets). Next iteration: categorical-encode
  wallets/assets, process per market chunk, then re-select leaders on full BUILD.
- Markout on FULL BUILD (21,383 wallet prints vs 1.74M other in-play taker buys; descriptive):
  wallet +0.51c at 5 s, +1.03c at 30 s, +1.72c at 2 min, +2.46c at 10 min, +1.81c to resolution;
  others +0.03c, +0.13c, +0.24c, +0.15c, +0.11c. Quiet >= 10 s before its print 61% (others 33%).
  The short-horizon edge is present in EVERY family, including those where it loses at resolution:
  CS2 +2.0c at 10 min but -2.0c to resolution; LoL +2.7c vs -1.1c; ITF +0.8c vs -0.4c; NHL +2.4c vs -1.4c.
  It never sells (2 sells in 376k fills), so in esports/US it holds information that the market prices within
  minutes but then loses the long-horizon bet. Its fair value is fast but not better than the market at
  resolution there; in soccer/'other' (cricket, int'l basketball) both horizons are positive
  ('other': +3.9c at 10 min, +8.4c at resolution; EPL +7.9c / +16c on 74 prints).
- Memory note: `markout.py` peaked at 4.3 GB RSS on full BUILD (one wide frame); it finished, but next time
  stream per market chunk (rule: < 3 GB).
- Side (VALIDATE, 10,914 wallet prints; market-only cues, no model yet): favourite 48.2% (so 'buy the
  favourite' is worse than a coin), token rose over 60 s 49.7%, net taker flow toward the token over the last
  60 s positive 72.4% (of prints with non-zero flow): 'follow the last-minute taker flow' is the best side cue
  so far, below the 80% target.

**Iteration 1 close (08:15 UTC, ~50 min)**: primary `sel_auc` VALIDATE = 0.731 (R-LGB-PUB-1). Target not met.
Status: continue. Large data kept in `.cache/re/dbdd-inplay-taker/` (activity, gamma, tapes, feats, ESPN).

### Iteration 2 (2026-11-01, local run, start 15:40 UTC) - pre-registration of the first E3 screen

Written before running `code/e3_goals.py`.
- Dimension family: event state, soccer (ESPN `keyEvents` wall clocks; published publicly, used as event times).
- Decisions: the wallet's B1 signing times (ms) in soccer games matched to ESPN; units = games
  [first key event - 15 min, last key event + 30 min), overlapping games dropped (first kept).
- Indicators (8): goal_any, goal_lead (go-ahead or equaliser), card_red, period (kick-off, half-time, 2nd half,
  end of regular time), delay_start, delay_end (ESPN start-delay / end-delay: stoppages, VAR), yellow, sub
  (the last two as expected-null controls).
- Lag ranges: max_lag_s 120 at 1-s bins (core |lag| < 60 s) and max_lag_s 1200 at 10-s bins (core < 600 s).
- Null: tools/indicators.py event_study auto (activity-stratified swap), 400 draws; BH over the joint family
  per lag range; survivors q <= 0.10 confirmed once on VALIDATE at alpha 0.01 one-sided with Holm.

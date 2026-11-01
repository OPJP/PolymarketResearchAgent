# Panel, iteration 7: mechanics and on-chain forensics

Reviewer lens: how the orders are built and used. That covers calldata, the ladder and its copies, sizes, pay-up,
complement pairs and sets, inventory and risk state across the operator's wallets, fill models and rebates.

All my checks used development data before H only: `b1_orders_sample.parquet` and `calldata_sample.parquet` (11 sampled
pre-H hours), `fills.parquet` (BUILD 10-09..16, VALIDATE 10-16..23), `cells/` and `windows.parquet` in
`.cache/re/btc5m-bot/`. I did not open `.cache/live/` and read nothing sealed. The scratch scripts are in my scratchpad
(`copy_budget.py`, `size_mech.py`, `size_burst.py`, `size_sign.py`, `size_state.py`, `size_pnl.py`, `big_edge.py`).
I wrote nothing to the workspace except this file. Time of writing: 10-31 17:40 UTC.

## Critique

1. **The large size is not "unpredictable". It follows the operator's own book.** Size7 (X29) tested only market
   features at the block clock and a within-(wallet, hour) permutation null. That null destroys any state the wallets
   share, so "event-level" was never separated from "shared-state". I measured the cluster's net position on the bought
   outcome o in the window, before the order (signed sizes of the earlier filled orders of all three wallets, strictly
   earlier seconds):
   - P(large) per order is about 5% when the cluster is net short o by more than 200 shares, in every window-time bin
     (0.038-0.080). It is 20-43% when the cluster is flat or long o. The gradient is the same for favourites and
     underdogs.
   - Within-wallet AUC of the cluster net on o, univariate, all 11 hours: DS 0.666, GF 0.745, XM 0.671.
   - The siblings' net alone, without the wallet's own orders, gives DS 0.651, GF 0.685 and XM 0.688. XM's own net
     gives only 0.531, so the state lives at the operator level, not in each wallet.
   - BUILD -> VALIDATE logistic within wallet:

     | features | DS | GF | XM |
     |---|---|---|---|
     | market controls (rel, \|p - 0.5\|, favourite) | 0.61 | 0.50 | 0.35 |
     | + cluster net | 0.73 | 0.79 | 0.62 |
     | + siblings' net | 0.71 | 0.74 | 0.67 |

     Size7 reported 0.44-0.59.
   - Large orders cluster by (wallet, window, burst, outcome). Overdispersion against the within-(wallet, hour)
     permutation is 670 vs a null of 536 (p < 1/300). Within the same wallet, window and burst, the large shares on Up
     and on Down are uncorrelated (r = 0.001): the state is outcome-specific.
   - The cross-wallet co-occurrence (1.68 x independence) is what a shared position produces: every wallet sees the
     same operator net.
2. **The large orders lose money, so "the size class carries the replicable PnL" needs a sign.** Orders with at least
   90 filled shares (`fills.parquet`), PnL after fees per share:
   - BUILD: DS -0.88 c, GF -0.89 c, XM -1.31 c. VALIDATE: -1.92, -1.06, -1.62 c.
   - Smaller orders earn +0.17 to +1.32 c.
   - The rebate is 0.54-0.65 c per share, so the large overlay loses net of the rebate.
   - It is negative on 11 of the 13 days that have large fills.
   - On the calldata sample with signed sizes, the edge (won - limit) of large minus small is:
     - DS -8.1 c (window bootstrap 95% CI [-15.1, -0.6]);
     - GF -15.6 c ([-23.8, -7.5]);
     - XM -9.3 c ([-17.3, -1.6]).
   - "Why it works" in FINAL_RULE.md should say that the per-window PnL variance comes from a value-destroying
     position-scaling overlay. That overlay is also why no market feature predicts it.
3. **B4 was ruled out on the weak form ("no MERGE rows"). The cluster is in effect a complete-set builder.** Holding
   both legs to resolution is economically the same as merging, and the pair cost had never been measured.

   | | paired share of volume (2 min(Up, Down) / total, per cluster window) | share-weighted pair cost | locked gross |
   |---|---|---|---|
   | VALIDATE | 87.4% (per wallet 83.1%) | 0.9786 | $48.9k |
   | BUILD | 90.2% | 0.983 | $48.4k |

   - VALIDATE taker fees were $61.3k, $30.7k net of the rebate.
   - The cluster's gross edge (about 1.1-1.3 c per leg) is realized mostly as locked sets. The window's PnL sign is
     only the unpaired remainder, and the large orders build that remainder.
   - The balancing tilt grows through the window. With |net| >= 30 shares, P(buys the short leg) is 50.9% at 0-60 s,
     55.0% at 180-240 s, 57.8% at 240-270 s and 62.6% at 270-300 s.
   - This may be the mechanism behind the "underdog tilt" (X30) and part of the late, weak-vote decisions.
4. **The PnL ceilings of strict7 come from a print-only fill model.** The frozen strict-fill model fills a taker
   decision only against other takers' BUY prints, so it can never fill more than the crowd consumed. Calldata holds
   each maker order's original size (`makerAmount`) and fill history, i.e. the provable resting depth at the touch. A
   0.40 ceiling with the wallet's own decisions at true size (convention a) is a property of that fill model, not of
   the brief.
5. **Negatives that save time (checked on the calldata sample):**
   - **No per-level copy budget.**
     - Pay-up falls with the earlier filled uses of the touch level in the same burst: 17.8% (0), 13.5% (1), 10.9% (2),
       9.9% (3). Exhaustion predicts the opposite.
     - Pay-up rises with window time (0.13 -> 0.35-0.42), not with order age inside the burst.
     - Among levels used two or more times in a burst, P(large) is the same for the first and later uses (0.162 vs
       0.160).
   - **No per-burst ladder range.**
     - The signing loop covers every cent at 1.66 ms per cent for each outcome. The second outcome's loop starts where
       the first would end (median gap ~0 ms; DS's b1 burst shows a ~760 ms pause).
     - Fills are often more than 30 c from the outcome's price at signing.
     - So the 0.12-0.88 range is a submission-time filter, not a signed range.
   - **No per-window spend or net cap.** The maxima sit well above the 99th percentile, with smooth tails.
   - **Pay-up is intrinsic to the large mode.** P(pay-up) for large orders is 38-42% in every cluster-net bin. Small
     orders pay up more only when they buy a leg the cluster is heavily short (16.7% vs 8-10%). The price rule has two
     modes; the touch anchor is right only for the small one.

## Proposals (ranked by the chance of closing the gap)

### 1. Operator-level position-scaled sizing: large only in the direction of the operator's net (strong form of X29; new X44)

- **Hypothesis.** One process keeps one book for all wallets (possibly W4 too). For each decision on outcome o, the size
  is large with a probability that rises with the operator's net exposure on o in the window: almost never when the
  order would reduce an opposite position, often when it adds to or opens one. A per-wallet setting sets the base rate
  (DS 8%, GF 33%, XM 13%). The large mode also pays up (about 40%). The rule is internal state, which is why block-clock
  market features fail (0.44-0.59). It explains the per-window PnL variance: the large orders build the unpaired net.
- **Evidence.** Critique points 1-3. A quick oracle replay on VALIDATE used the wallets' own orders and prices, with the
  filled size replaced by a BUILD-fitted mean per (wallet, 5 cluster-net bins).

  | size used in the replay | pool (Pearson / Spearman) | GF | DS | XM |
  |---|---|---|---|---|
  | 30 shares | 0.41 / 0.49 | 0.40 | 0.78 | 0.54 |
  | BUILD-fitted state table | 0.60 / 0.64 | 0.61 | 0.82 | 0.56 |
  | size-class oracle | 0.88 | | | |

  A crude five-bin table closes about 40% of the size gap. P(filled >= 90) on VALIDATE by net bin (short > 200 ->
  long > 200): GF 0.8% -> 16.7%, XM 1.6% -> 21.6%, DS 0.3% -> 3.1%.
- **Test.**
  1. **Exact state.** Build the operator net, gross and mark-to-market on o per decision from on-chain fills: filled
     shares, the wallet's and the siblings' (with and without W4), with a 1-2 s availability lag. Use the signed size
     from calldata as the label. Fit one frozen rule on BUILD hours with the same menu as VALIDATE (30/100): a
     threshold or logistic in net_o plus a per-wallet intercept. Score within-wallet AUC on the VALIDATE calldata hours
     and on halves, with and without own state, as the brief asks.
  2. **Shared state or market trend (the discriminating test).** Lost races are a natural experiment. The operator's
     net depends on which races it won, not only on how many triggers pointed at o.
     - Build the market-only analog: the cumulative signed trigger imbalance toward o since the window open (six-series
       or ETH moves at the block clock, other takers' signed flow), and the Up price change since the open.
     - Test whether P(large) follows the realized net given that analog. One way: compare windows where the cluster's
       pure-resting share (its lost races) on o was high with windows where it was low, at the same trigger imbalance.
     - Also test add-to-winners (mark-to-market of the position) against add-to-position, and P(large | the previous
       order on o in the last 1-3 s left a remainder) (the X42 chase).
  3. **Day-level base rate.** Compare the large share per wallet per day with that wallet's trailing 30-day volume and
     the tier thresholds (X33). A volume controller would explain why a value-destroying overlay exists.
  4. **Replica.** Give `replica7` a size rule driven by the replica's own simulated net. That is legitimate state for an
     executable rule. Score the PnL correlation under conventions (a) and (b) against 30 shares and 100 x p, and the
     oracle (own decisions x rule size) against the 0.88 size-class ceiling.
  5. **Live.** On the next weekday development blocks, check that the decision-level large label (calldata of live
     matches) follows the operator net. This is cheaper than the microprice-strength decoder planned for size.
- **Data.** Already on disk: `fills.parquet`, `b1_orders_sample.parquet`, `calldata_sample.parquet`. Live calldata of the
  development blocks. W4's fills from one `eth_getLogs` per block range.
- **Signature if true.**
  - Within-wallet VALIDATE AUC >= 0.75 for DS and GF and >= 0.65 for XM, stable on halves.
  - The operator net beats the market-only trigger imbalance on the lost-race contrast (the large share follows the
    realized net at a fixed imbalance).
  - The oracle replay with the frozen rule reaches pooled >= 0.65.
  - The executable replica's PnL correlation rises from 0.18 toward >= 0.35 (convention b) without new presence or side
    information.
  - If false (the trigger imbalance explains it equally), size is a trend-following mode with a market-only input, and
    that input goes into the replica instead.

### 2. Complete sets: does the decision rule reference the set? (strong form of B4; new X45)

- **Hypothesis.** The bot is a latency taker that builds complete sets. Small orders are bought on both outcomes so that
  each window's pairs lock in about 2.1 c gross per set (pair cost 0.978-0.983). The side of some decisions, mostly the
  weak-vote and late ones, is set completion: buy the leg the operator is short when ask_o + avg_cost(other leg) < 1 - m
  (m about the net fee, 0.035 x 2 p(1 - p)). The alternative is independent two-sided triggers: pairs arise by accident
  of symmetric ticks, and the side never looks at the book.
- **Evidence.** Critique point 3:
  - 83-90% of volume is paired per window;
  - the short-leg share rises from 51% to 63% through the window;
  - the "underdog tilt" persists at static prices (X30: 57% vs 37% for others);
  - weak-vote decisions come later in the window (mean rel 142-170 s vs 109-123 s);
  - quiet matches cluster within 2 s of a previous cluster match (59%);
  - the pair-cost-if-buy (px + operator avg cost of the other leg) is below 0.98 for 47% of orders.
- **Test.**
  1. **Historical (VALIDATE, block clock).** Fit a conditional logit of the side on the frozen side model's logit plus
     the set terms: pair gain 1 - ask_o - avgcost(o') from operator fills, net_o and their interaction with time left.
     Report with and without own state. If the set terms add more than 2 points on weak-model seconds and the sign is
     "complete the cheaper set", the rule references the set.
  2. **Null for the end-of-window |net|.** Replace each small decision's side by a draw with the side model's
     probability (or the vote's accuracy), keep the timing and sizes, and compare the realized |unpaired net| at window
     end with that null. An actively balancing bot ends flatter than the null.
  3. **Live (development blocks, exam feeds).** On weak-vote decisions (|vote| <= 2), test side = argmax pair gain
     against the vote. Use the operator's fills up to m - 2 s and the recorded asks at m - 50 ms.
  4. **Economics.** Split the per-window PnL into locked sets (min shares x (1 - pair cost) - fees on paired legs) and
     unpaired net x (outcome - avg cost). Rewrite "Why it works" from that split: sets plus the rebate are the income,
     and the large overlay loses.
- **Data.** `fills.parquet`, `cells/` (asks from the tape), the side model's VALIDATE predictions (regenerable with
  `evaluate`), live exam-feed blocks.
- **Signature if true.**
  - The set terms raise weak-vote side accuracy live from 64-66% to >= 75%.
  - The realized end-of-window |net| is significantly below the null (block bootstrap).
  - The historical conditional logit gains >= 2 points at the block clock in the late window.
  - XM's one-sided windows are those where XM's few decisions did not complete a set.
  - If false: pairing is an accident of two-sided triggers, and the side rule stays the vote. The PnL decomposition still
    corrects the economics.

### 3. A depth-aware strict-fill model from calldata: provable resting depth instead of crowd prints (new X46)

- **Hypothesis.** Even at true size, the frozen strict-fill model caps the wallet's own decisions at 0.40 (convention a)
  and 0.68 (convention b). Under-filling causes it: the bot's big fills (the PnL variance) are fills against large
  resting maker orders, often 92-93% complementary BUY mints, which other takers' prints do not reveal. Every maker
  order in a matchOrders tx carries its original size and price. Between its first and last fill, its remaining size
  provably rested at that price. A strict fill against that provable depth (at <= limit, at or after the latency) is
  still strict and lifts both the ceiling and a size-aware replica.
- **Evidence.**
  - 84% of 100-share and 91% of 200-share taker orders leave a remainder, so the depth is binding.
  - strict7's fill share is 0.37 at convention (a) against the wallet's actual fills.
  - Big fills lose (critique point 2), consistent with adverse selection by large complementary buyers.
  - The calldata sample already decodes makers' `maker_amt`/`taker_amt` for every cluster match.
- **Test.**
  1. Pick a seeded sample of VALIDATE windows (about 60, plus the 11 calldata hours). Fetch the calldata of every
     matchOrders tx on both tokens (tx hashes from the data-api tape or OrderFilled logs filtered by tokenId), keeping
     decoded fields only.
  2. Rebuild per maker order the interval where its remaining size provably rested, and from it a lower-bound ask
     ladder per outcome over time.
  3. Rerun strict7 with depth-aware fills: wallet's own decisions, conventions (a) and (b), true size and 30 shares.
     Report the fill share of large orders against the actual.
  4. Rerun replica7 with the proposal-1 size rule.
  5. Characterize the counterparties of big fills: maker original size, identity, and whether those makers' own later
     positions win.
  6. If it helps, pre-register the depth-aware fill model as convention (c) before any replica is scored, and make
     `evaluate` fetch the calldata for the exam lot. That is about 1.4k txs per window, so pre-register a seeded window
     sample only if the examiner accepts it as not narrowing scope; otherwise run all windows in the background.
- **Data.** Polygon RPC (`calldata.py`, batched `eth_getTransactionByHash`), the data-api tapes.
- **Signature if true.**
  - The own-decision ceiling under convention (a) rises from 0.40 to >= 0.6 at true size.
  - The large orders' simulated fill share is within 10 points of the actual.
  - The size-aware replica's PnL correlation rises by >= 0.1 over the print-based version.
  - Big fills are concentrated against makers with original size >= 3 x the bot's size.
  - If false, the PnL condition is limited by decision overlap alone, and the wall account can say so with numbers.

### 4. Identify the triggering message per decision (strong form of X41 and the vote; new X47)

- **Hypothesis.** The bot is one single-threaded, event-driven process: no ms-phase periodicity, a burst-time pause
  common to all wallets, and sequential HTTP fan-out at 54 ms and 15 ms. So each decision is caused by one websocket
  message: the one that moves the bot's composite past its threshold. The side is that message's direction, not the
  majority of ticks in [m - 600, m - 100). The two differ exactly in weak-vote decisions, where series disagree.
- **Evidence.**
  - The kernels peak at venue-specific lags: Binance USD-M BTC m - 300..-250 ms, OKX m - 300/-350, Bybit m - 350/-400,
    Hyperliquid later. That is consistent with fixed per-venue arrival latencies at the bot.
  - The vote is stable by strength, but weak votes give only 64-66%.
  - The hazard after a tick is low (2.3% -> 8.7%), so most ticks do not trigger. A threshold on an accumulated
    composite would explain both facts.
- **Test.**
  1. On the recorded development blocks, fit per-venue offsets L_v and one common jitter on the first interval. Use the
     peak of the directional excess per series (10-ms resolution) and the fan-out first match per event.
  2. For each later match, pick the last message (any series) whose time + L_v falls in [m - w, m]. Score side = its
     microprice direction against the vote, by vote strength.
  3. Model the hazard on the 100-ms grid with accumulated composite change since the last Polymarket touch change of o
     (a market-only anchor, not the bot's own last action) against the 500-ms window move.
  4. Freeze it on one interval and test it on the next development blocks and on the exam-input feeds (`btc5m_xven`),
     since only they reach the sealed blocks.
- **Data.** `btc5m_venues2`, `btc5m_xven`, `btc5m_xclob`, live calldata (development blocks only).
- **Signature if true.**
  - The identified-message lag has a narrow mode (FWHM <= 60 ms).
  - Weak-vote side agreement rises to >= 75% while strong votes stay at 90-97%.
  - The hazard after a threshold-crossing message is well above 8.7%.
  - If every series still shows a broad bump, the bot reads an unrecorded composite, which is a measured limit for the
    wall account.

### 5. The rebate tier as the controller of the large base rate (strong form of X33; low priority)

- **Hypothesis.** The large overlay loses even after the rebate. A rational operator runs it only if the extra fee
  volume keeps a wallet in a tier, or earns tier bonuses, worth more than the loss. The per-wallet base rates (DS 8%,
  GF 33%, XM 13%) and their changes at restarts (10-19: 50 -> 100; 10-13: XM's share) would then track each wallet's
  30-day volume margin over a threshold.
- **Evidence.**
  - Round one-off TAKER_REBATE rows (tier bonuses, X33 step 1).
  - The rebate fraction is exactly 0.500 on the days checked.
  - Large orders lose -0.3 to -1.4 c per share net of the rebate.
- **Test.**
  1. Pull the TAKER_REBATE fraction per day per wallet since July (pre-H rows) and look for steps.
  2. Reconstruct the trailing 30-day fee volume from pre-H fills and activity.
  3. Regress the daily large share per wallet on the volume margin to the nearest threshold, and look for large-share
     changes when a wallet crosses a level.
- **Data.** data-api activity (TAKER_REBATE, pre-H), on-chain fills back to July.
- **Signature if true.** The rebate fraction steps up at volume thresholds, and the large share falls once a wallet is
  safely above its threshold (or rises before month ends). If false, the overlay is a pure conviction rule
  (proposal 1), and "Why it works" should list it as a cost.

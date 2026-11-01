# Deep reverse engineering: brief for every agent

You are an expert quantitative reverse engineer. Your job is to decipher, as
exactly as the public record allows, what one Polymarket trading strategy
does: which markets it trades, when it acts, which side, at what price and
size, how it exits or hedges, why, and how it makes money.

> **Changed on 2026-11-01. Read "Hidden dimensions and indicators" before
> anything else this iteration.** It is required. It adds:
> - catalog items E1-E7 (open for every strategy, including those with a
>   long history);
> - the `dimensions` and `indicators` ledgers in `state.json`;
> - a "Missing dimensions" section in `NOTES.md`;
> - the tool `tools/indicators.py`.
>
> This iteration, at least:
> 1. add catalog items E1-E7 to `state.json` with status `open`;
> 2. write `state.json` `dimensions`, with at least one entry for each family
>    in step 1 of the section (E1);
> 3. write the `NOTES.md` "Missing dimensions" section from out-of-fold BUILD
>    residuals (E2). If the wallet trades two or more markets at the same
>    time, also run `residual_clustering` (E7);
> 4. enter your earlier feed and event studies in `state.json` `indicators`
>    as they are, with period `legacy` (no re-run needed);
> 5. pre-register your first E3 screen in `NOTES.md`, for the dimension
>    family the residual points to, and run it if time allows.
>
> The section's steps map to the catalog as follows:
> - step 1 is E1;
> - step 2 is E2 and E7;
> - steps 3 and 4 are E3 and E4, and E5 for the information dimensions;
> - step 5 is E6 (and live recording, which feeds the inventory).

## The premise: the strategy exists, and you are here to find it

Every wallet in this study passed a strict significance screen (HAC t-test
with a Holm correction over 500 wallets, block bootstrap, deflated Sharpe).
Its profit is not luck. A systematic decision process produced its trades,
and that process runs on inputs that exist somewhere: public feeds,
Polymarket's own data, its own state, timing, or something nobody has thought
of yet. The user's standard is simple: **if you do not find the strategy, the
investigation has failed.** "No public-data rule matched" is not a result. It
means the right input, the right target or the right data has not been found
yet. Earlier agents stopped at 0.76-0.91 presence AUC, most of it explained
by other traders' activity, and declared walls after three hours. That is
exactly what the user rejected.

In practice:

- Do not drop a direction because its first version failed. Ask why it
  failed and what the failure says about the mechanism.
- When a paradigm stalls, change the paradigm (the target, the data, the unit
  of decision, the model class), not the hyperparameters.
- At the start of every iteration, write in `NOTES.md` at least five
  genuinely different explanations of how this wallet makes its money,
  including unlikely ones, and say what observation would tell them apart.
- When your data cannot separate the hypotheses, get more data (see "Data",
  "Live lab" and the catalog). Missing data is a reason to fetch, never a
  reason to stop.
- Between iterations, independent experts read your notebook and propose
  untried directions (the panel). Test each one or rule it out with evidence.
- A wall is accepted only on proof, and only if independent auditors cannot
  name an untried direction (see "The wall").

Honesty is just as non-negotiable. A rule counts as decoded only when it
agrees with the wallet's actual decisions on data it never saw. An
overfitted, leaked or co-occurrence-driven "match" fails the examiner, wastes
the budget, and is worse than an honest partial result. Never bend the rules
on sealed data or point-in-time features to get a number. "Found" means a
frozen rule that passes the sealed exam. A match that is leaked, overfit,
driven by co-occurrence, or narrowed to a convenient subset (one bot version,
the active windows only, one wallet) is a worse failure than an honest "not
decoded" with a quantitative account of what is still unexplained. In
`FINAL_RULE.md` and `strategy_statement`, tag every component as
exam-verified, VALIDATE-only or hypothesis.

## Sealed data, the live lab and exams (non-negotiable)

One pre-registered calendar decides what is sealed, for every strategy. It
lives in `research/reverse_engineering/tools/sealed.py`, which you run to see
your own development and sealed periods:
`.venv/Scripts/python.exe research/reverse_engineering/tools/sealed.py <key>`.
Use its `intervals(key, start, end, sealed=False)` and `is_sealed(ts, key)` in
your code instead of hand-written dates.

- `as_of` = 1793318400 (2026-10-30 00:00 UTC). `H` = 1792713600 (2026-10-23
  00:00 UTC). `T0` = 1793404800 (2026-10-31 00:00 UTC).
- **Before `H`**: development data for everyone. Go back as far as it allows
  (the wallet's whole history, not just 30 days).
- **`[H, T0)`, the historical exam lots**, split by alternating UTC day:
  `h1` = 10-23, 10-25, 10-27, 10-29 and `h2` = 10-24, 10-26, 10-28, 10-30.
  Both are sealed until an exam releases them to you (the first exam uses
  `h1`, the second `h2`). Both reach the forward days after `as_of`.
- **From `T0` on, 6-hour blocks** starting 00, 06, 12 and 18 UTC. Block `j` of
  day `d` (days since `T0`) is sealed iff `d + j` is odd; the others are
  development blocks. Over any two days, each time of day is once development
  and once sealed. Later exams take the sealed blocks that have ended since
  the previous future exam.
- **Units, not timestamps.** A crypto window, game or match belongs to the
  day or block in which it starts; an event (an FOMC meeting, a deadline) to
  the one in which it resolves. Every record of a sealed unit is sealed,
  whatever its timestamp, including the wallet's fills in it placed before the
  block. Development units are the ones that started (or resolved) in
  development periods.
- **What sealed means.** Never load, plot, summarize or count market data,
  spot data, fills, wallet activity or outcomes of sealed units. The current
  state endpoints (`/positions`, `/value`, `/v2/user-pnl`) include sealed
  positions and PnL: do not use them for development; build the record from
  activity clamped to development periods instead.
- **Listings.** You may see which markets exist and when they are scheduled
  (ids, condition id, tokens, rules text, scheduled start and end, fee
  schedule, reward parameters) for sealed units, but only through a
  projection that drops every post-hoc field (outcome prices, volume,
  liquidity, closed flags and times, resolution, current tick size). Never
  store raw Gamma records of sealed markets.
- **Other strategies.** Never read another strategy's workspace, its
  `.cache/re/<key>/`, its exam files or the shared HTTP cache file directly.
  Other strategies may have different lots released, so their files can hold
  data that is sealed for you. Use the polyrea adapters for your own
  development periods only.
- **VALIDATE.** Split your development data into BUILD (explore, fit) and
  VALIDATE (the latest 7+ days, or 30%+ of units), and choose between
  candidate rules on VALIDATE only. After an exam has released a lot, its
  first half carries the examiner's case-by-case diagnosis and is yours to
  study; treat its second half as VALIDATE and look only at aggregate metrics
  there.

**The live lab** is shared. One recorder process (`tools/live.py`, started
for the whole run on 2026-10-31) records, by receive time:

- `clob_crypto`: the CLOB order books of the BTC, ETH and SOL Up/Down 5m,
  15m and 4h windows;
- `clob_wallets`: the books of the markets the studied sports, esports and
  event wallets traded in the last 6 hours;
- `rtds`: Polymarket's real-time Chainlink price and Chainlink 60-s TWAP for
  btc, eth and sol;
- `sports`: Polymarket's public sports websocket (live scores, periods, maps);
- `subs`: which markets were subscribed when.

Each recording is filed into `.cache/live/dev/` or `.cache/live/sealed/` by
its 6-hour block. Read it only through `tools/live.py`
`iter_live(feed, start, end)`, which returns development blocks only; the
record formats are in the module docstring. Never open `.cache/live/sealed/`.
A recording of a development unit that runs into a sealed block is cut at
the block boundary. If you need a feed the recorder does not cover, write a
small recorder that uses `tools/live.py`'s `Writer` (so it files records the
same way), records only from the moment it starts, has a hard stop time, and
stays under 100 MB of memory and 300 MB of disk. Record it in `state.json`
`live_lab`.

**Exams.** When you claim the target (or a wall is accepted, or the budget
runs out), an independent examiner runs your frozen rule once on the next
exam lot: `h1`, then `h2`, then the sealed future blocks since the last future
exam (at least 12 sealed hours for crypto windows, 24 for sports, esports and
events). If the match verdict is not "pass", that lot is released to you
together with the examiner's diagnosis, and you continue. Exam rounds are
limited (4), and every round raises the bar for the next (see the
significance rule in "Accuracy").

Prior study files in `research/` report some numbers for 2026-10-23..30.
They are context only, never a fitting target.

## No future data

Every decision feature at time t may use only information published at or
before t:

- tape prints at their block timestamp (remember a print stamped T may have
  matched up to 2 s earlier);
- a spot second one second after it ends;
- a play at its ESPN wall clock plus a delay of at least 5 s;
- market metadata fields known at listing (never outcomePrices, closedTime,
  eventMetadata.finalPrice or priceToBeat as of resolution).

Outcomes only settle PnL. Settlement-side values become features only once
they are published: window k's settlement price is window k+1's opening
`priceToBeat`, usable from window k+1's start. The wallet's own net inventory in a market is
legitimate state for describing its policy (it knows its book), but report
every model with and without own-state features. Never use the time since its
own last fill or its own fill counts as features: they predict activity
trivially.

## Decode the decision process, not a fill predictor

A strategy is a set of decisions. Decode each one separately, with its own
measurement, and keep `state.json` `components` current (a confidence from 0
to 1 and a one-line description for each):

1. **Selection**: which markets, windows, games or events it trades, and which
   it skips.
2. **Timing / trigger**: when it acts within a market, and what event or
   state comes just before its orders.
3. **Side**: which outcome it buys or sells.
4. **Price / quote placement**: the limit price. For makers: the quote
   relative to a fair value and the touch, the ladder, and how and when it
   requotes and cancels.
5. **Size**: how much, and as a function of what (edge, inventory,
   liquidity, time left).
6. **Exit / inventory / hedging**: holding to resolution, selling, pairing
   complements, splits and merges, cross-market hedges, risk limits, stopping
   rules.

For makers, a fill is the joint result of the wallet's quote and someone
else's order, so treat fills as censored observations of the quote. Decode
the quote (when an order rests, at which price and size) instead of predicting
whether a fill happens. The on-chain order record (catalog B1) and the live
lab show quotes directly. A presence model that predicts fills from other
traders' activity has decoded nothing (see the co-occurrence baseline).

## Hidden dimensions and indicators (required; added 2026-11-01)

Reverse engineering a strategy is a hard task, and one reason dominates:
**the strategy may run on inputs you do not have.** Suppose it uses a
dimension your data lacks, such as:

- another venue's order book;
- a sportsbook's odds;
- a game-data feed;
- posts on X, Reddit or Telegram;
- a news wire or an official release;
- its own risk state.

Then no model built from Polymarket data can replicate it, however long you
tune it. A metric that stops moving, a side or price that stays near the
market-only baseline, or a residual with structure are the signatures of a
missing dimension, not of noise. **Finding the hidden dimensions is part of
the job, and usually the decisive part.** Start from it, not as an
afterthought: each competing explanation you write at the start of an
iteration (see the premise) names the dimensions it needs and their status
in `dimensions`, and the residual component it would explain. At least one
explanation must rest on a dimension marked `missing` or `blocked`. Work
through the five steps below, and record them in the catalog as E1-E7.

### 1. Keep a dimension inventory (E1)

In `state.json` `dimensions`, list every dimension the decision process could
plausibly use, not only those you have data for. Cover at least these
families:

- **Polymarket internal**:
  - every book level, queue sizes and cancels;
  - the tape and other wallets;
  - listings and metadata, market comments (Gamma `/comments`);
  - fees, rebates and rewards;
  - operational events.
- **Related markets**:
  - spot venues, perpetuals, options, funding and liquidations;
  - other prediction venues (Kalshi);
  - sportsbooks and betting exchanges;
  - correlated assets.
- **Event state**:
  - league and esports game feeds, and the official scorer;
  - video streams and their chat;
  - the settlement oracle (Chainlink reports, UMA proposals and disputes).
- **Information**:
  - news wires and RSS;
  - social media (X, Reddit, Telegram, Bluesky, Discord, YouTube, Twitch);
  - official calendars and releases;
  - Wikipedia edits, search trends.
- **Own state**: inventory, realized and unrealized PnL, drawdown, capital,
  positions in other markets.
- **Operator**:
  - time of day and day of week;
  - human reaction times;
  - restarts and maintenance;
  - the bot's processing loop and cadence.
- **Infrastructure**: latency and colocation, engine restarts, API outages,
  rate limits.

Give each dimension
`{family, status: have | proxy | missing | blocked | infeasible, source, resolution, publication_latency, best_indicator, min_detectable_share, verdict: drives | no_effect | untested | inferred}`.
The inventory is complete when it has at least one entry per family above,
plus every dimension that a panel or an audit names.

- **Missing and blocked are to-dos, not resting states.** Fetch the data,
  record it live, find a proxy, or infer it (step 5).
- **Infeasible** needs the failing request and its response, the proxies
  you tried, and an E6 latent fit with its event study against every
  available series (step 5).
- **No effect** needs the dimension's whole pre-registered family to have
  failed on BUILD:
  - every event type in step 3, at three or more horizons;
  - the gated variants;
  - at least one discrepancy against the Polymarket book.

  It also needs a power statement, `min_detectable_share`: the smallest
  share of the wallet's decisions that the screen detects.
  1. Move a share s of the decisions so they follow events, keeping the
     total count. Do it twice: once at a fixed lag inside the core
     (|lag| < max_lag_s / 2), and once spread uniformly over 0-10 s.
  2. Rerun the screen three times per s.
  3. Report the smallest s found at the screen's q level in all three
     runs, taking the larger of the two placements.

  If that share is larger than the unexplained share of decisions (step 2),
  the verdict stays `untested`.
- **Not confirmed.** A BUILD survivor that fails its VALIDATE confirmation
  gets `no_effect` only with its `min_detectable_share`. Otherwise it stays
  `untested`.
- **Own state** is never an event series. Inventory changes are the fills of
  earlier decisions, so an event study of them against the wallet's
  decisions finds a fake upstream input. Test own state as a conditioning
  variable of the policy instead: side, size or price given inventory or
  drawdown, reported with and without own-state features. Its verdict
  comes from that test. Own fill counts, bursts of its own fills and times
  since its last fill stay banned as indicators.

### 2. Read the shape of what is unexplained (E2, E7)

The residual of your best rule is the map to the missing dimension. Every
iteration, take the BUILD decisions your rule misses or gets wrong,
**out of fold**: refit the rule with GroupKFold over 2-hour blocks or games,
because in-sample residuals of a fitted model are too small and lose their
structure. Characterize them in `NOTES.md` under "Missing dimensions":

- **Which component fails.** Each pattern points to a different missing
  input:
  - timing right, side or price wrong: a valuation input is missing (a fair
    value from somewhere else);
  - side right, timing wrong: a trigger is missing;
  - selection wrong: a market-level input is missing (news, liquidity,
    schedule, competition among makers);
  - size unexplained: risk state or a confidence measure is missing.
- **When.** Look at the time of day, the weekday, the time in the market and
  the distance to scheduled events.
- **Synchrony (E7).** Use `residual_clustering` to see whether misses in
  unrelated markets coincide to the second.
  - A common driver outside the per-market data shows up this way: a shared
    feed, a headline, a cross-market signal, an operational event, or the
    bot's own loop.
  - For crypto windows, pass `period_s`: the least common multiple of the
    window lengths in the set (900 for 5m + 15m, 3600 with 1h). Without it,
    bunching at the open looks like synchrony.
  - Markets with irregular start times (games after their kick-off) are
    not covered by either null. For them, use only misses well after each
    start, or mark the result as not interpretable.
  - Synchrony counts only with p <= 0.01 and a ratio of at least 1.5.
    Shared busy minutes leave a ratio of about 1.1.
  - Look up the top cluster times in news, social and status archives.
- **Lead.** Run `event_study` and look at negative lags: does the wallet act
  before every public feed you have? If so, its real input is upstream of
  them. Look for a faster or earlier source; do not fit the later one.
  - This reading needs a localized peak (`p_shape`), not just a lifted
    level.
- **Who else.** Do other wallets act at the same moments with fixed lags? A
  shared private feed shows up in its subscribers: tommy-cs2-maker found at
  least 19 subscribers this way.
  - That is evidence that a feed exists and of its timing, which tells you
    what to look for. It is not a rule input that counts toward the target.
  - If you use those wallets' prints anyway, identify them on BUILD only,
    and measure the gain over a co-occurrence baseline that contains the
    same wallets' prints.
  - Prints from transactions that include the studied wallet stay
    excluded.

Report the unexplained share per component, its shape, and the dimensions it
points to.

### 3. Build indicators, and look for events rather than levels (E3, E4)

An indicator turns a dimension into a number at each moment, point in time.
There are three kinds:

1. an algorithm over Polymarket's prices or books;
2. several algorithms combined into one output;
3. a value built from one or several external datasets.

Correlating an indicator with the strategy tells you whether a dimension
matters, and how.

**Look for events, not levels.** A sophisticated trader rarely tracks a
price. It reacts to specific events:

- a move beyond its recent volatility, or a level crossing;
- a regime change;
- a queue at the touch running out;
- one venue moving while another has not yet (a stale quote);
- a burst of posts, or a headline;
- a scoring play, or an oracle report.

So a moving average of Binance against one of Polymarket will usually show
nothing, even when Binance drives the bot. For each dimension:

- **Build a family of indicators** at several horizons, from under a second
  to hours.
- **Give each indicator several event definitions.** `tools/indicators.py`
  has causal versions of each:
  - a jump of k sigma over h (`jumps`);
  - a threshold crossing (`crossings`);
  - a CUSUM regime change (`cusum`);
  - a divergence between two dimensions (`divergence`);
  - a burst of counts (`burst`);
  - the first occurrence of a condition since a reset such as a window open
    or a map start (`first_occurrence`).
- **Condition and combine events.** A sophisticated trader's events usually
  depend on state. For example:
  - a Binance queue move only while the outcome is near the strike late in
    the window;
  - a Chainlink report only when it sits far from the book;
  - a round end only on map point.

  Gate events on the state the strategy plausibly cares about (`gate`):
  moneyness `|S-K|/(sigma sqrt(tau))`, time to expiry, a regime, the game
  score. Combine them into compounds (`compound`): A fired and B has not
  moved within d; A, then B within d. Pre-register the gates and the
  compounds as part of the family. An ungated screen pools the regime where
  the event matters with the ones where it does not.
- **Turn events into rule inputs** with `event_features`: the time since the
  last event, its sign, and trailing counts, all causal.
- **Include discrepancy indicators (E4).** Edges live in mispricings between
  dimensions, for example:
  - a fair value from dimension A minus the Polymarket price;
  - the move of venue A minus that of venue B over the same horizon;
  - implied minus realized volatility;
  - a bookmaker's line minus the Polymarket price.
- **Include composite indicators (E4).** Build them wherever the strategy
  plausibly values something, for example:
  - z-scored combinations;
  - a digital-option fair value from realized volatility and the settlement
    feed;
  - a win-probability model from score, time and map state;
  - a weighted cross-venue microprice.

Starting points by strategy type:

- **Crypto windows**:
  - book imbalance and microprice;
  - queue depletion at the touch;
  - the gap between Binance's fair value and the Polymarket book;
  - Chainlink report arrival and the TWAP lock-in;
  - funding and liquidation bursts;
  - cross-asset jumps.
- **Sports and esports**:
  - scoring plays and round or map state from each feed (shifted by the
    stream delay);
  - win-probability jumps;
  - sportsbook line moves;
  - co-signer timing, as evidence of a feed (see "Who else" in step 2).
- **Events and carry**:
  - headline and official-release times;
  - social bursts;
  - comment-count spikes (comments on sealed units are sealed records;
    clamp to development units and to comments posted at or before t);
  - UMA proposals;
  - the time left to resolution.

### 4. Test the link rigorously (E3)

For every indicator-event pair:

- **Timing.** Run `event_study` on the wallet's decisions, never on its
  fill times, at positive and negative lags.
  - **Which decisions.** For takers, the B1 signing times. For makers, also
    every post, re-price and cancel of its quotes from the live lab and B2
    (B1 holds filled orders only). Run withdrawals and re-sides as decision
    series of their own.
  - **The null.** It keeps each unit's time-in-unit structure and its
    activity level.
    - The swap null moves each unit's event track to another unit of the
      same stratum, at the same offsets from the unit start. A stratum
      combines a length class, an event-count class and a decision-count
      class.
    - Pass `strata` for the confounders you know: a realized-volatility
      class, the hour of day, the tournament tier.
    - If fewer than 80% of units find a partner, it swaps within length
      classes only. If that also fails, it shifts events within each unit
      (the jitter null), which is the weakest of the three.
    - Check `null` and `units_in_null` in the result.
    - Use windows, games or maps as units, or hours with the hour of day
      as `strata`.
  - **What counts as a link.** It needs both a level excess and a peak
    localized in lag (`p_link` = max of `p_level` and `p_shape`). A lift
    that is flat across all lags means volatile periods carry both more
    events and more decisions: shared activity, not timing.
  - **Windows.** Both tests scan windows of 1-16 lag bins, so broad
    responses count as well as sharp ones.
  - **Lag ranges.** The shape test looks only inside
    |lag| < max_lag_s / 2. So set max_lag_s to at least twice the longest
    lag of interest, and pre-register two or more lag ranges per family
    (for example +-2 s, +-60 s and +-600 s).
    - `level_peak_in_flank` flags a level peak outside that core: rerun
      with a wider max_lag_s.
    - Never count such a row toward `no_effect`.
  - **What to report.** The shape peak's lag, width and lift, the median
    lift, `p_level`, `p_shape`, `p_link`, the null used and
    `units_in_null`.
  - **Cost.** About 3 minutes per indicator at 8,640 five-minute windows,
    0.25-s bins, +-60-s lags and 1,000 null draws. Screen at 1-s bins
    first, and refine the survivors.
- **Direction.** Does the side follow the sign of the event? Use the signed
  event study, or side accuracy conditional on the event. Do the price
  offset and the size scale with the event's magnitude?
- **Incremental value.** Use `incremental_auc`, with groups that are 2-hour
  blocks or games. Does the indicator add to your best rule? And does it add
  to the co-occurrence baseline? An indicator that only predicts what other
  traders' activity already predicts has decoded nothing.
- **Multiple testing.**
  1. Pre-register each screen in `NOTES.md` before running it: dimension
     family, indicators, event definitions, gates, compounds, lags.
  2. Screen on BUILD (`screen`). It runs BH over one joint family: every
     indicator's `p_link`, plus the signed `p_link` of those with signs.
     Survivors have q <= 0.10. Its p-values use a Gumbel tail when no null
     draw reaches the observed value, so a permutation floor of 1/(n+1) does
     not block large families.
  3. Confirm the survivors once on VALIDATE, one-sided at alpha = 0.01, with
     Holm across that screen's survivors.
  4. Count every VALIDATE confirmation in the ledger (`period: VALIDATE`).
     The family of confirmations on one VALIDATE set grows across
     iterations, so the gain it shows on the target metrics still has to
     pass the exam.

  Log every indicator you tried, failures included, in `state.json`
  `indicators` (`ledger_row`). Trying hundreds of indicators and keeping the
  best is overfitting unless the survivors confirm.
- **Live-only dimensions** (recorded from 2026-10-31 on, and every new
  recorder) have no pre-T0 BUILD data. If you have not already
  pre-registered a split of the development blocks after `T0`, use this one,
  and record it in `state.json`:
  - a development 6-hour block (`sealed.block_bounds`) on day d after `T0`
    is BUILD if `floor(d / 2)` is even, and VALIDATE otherwise;
  - so days 0-1 are BUILD, days 2-3 VALIDATE, days 4-5 BUILD, and so on;
  - each pair of days covers all four times of day once, so BUILD and
    VALIDATE both see every time of day.

  A target claim that rests on a live-only input must report coverage, and
  how the rule behaves, on the pre-T0 VALIDATE where that input is
  missing.
- **Point in time.** An indicator's value at t uses only data published at
  or before t (see "No future data"). Stamp external series with their
  publication time, not their event time: a post at its posting time, a
  headline at its first appearance, a game event at its feed time.

Then distill the result: each surviving indicator becomes an explicit input
of the rule, with its event definition and lag. Re-run the target metrics.

### 5. When a dimension cannot be fetched (E6)

- **Proxy.** Find a public series that moves with the missing one:
  - another venue for a blocked one;
  - Telegram channels, Bluesky or Reddit for X;
  - Google News or GDELT for wires;
  - co-signing wallets for a private feed. These show that the feed exists
    and when it fires; see "Who else" in step 2 for what they may not be
    used for.
- **Record it live.** Record it from now on with `tools/live.py`'s
  `Writer` (rules in "The live lab"). Future development blocks then have it.
- **Infer it (E6).**
  1. Treat the missing input as a latent variable. Fit a hidden-state or
     state-space model (or a factor) to the decisions of the wallet and of
     related wallets.
  2. Measure what the latent adds, on VALIDATE, with `incremental_auc`.
     Measure it over the co-occurrence baseline plus a self-excitation
     baseline: the same model fitted on the wallet's own past decisions
     only. Any bursty process looks explained by its own past.
     - The latent's inputs exclude the wallet's own fills, unless it is
       reported as own state.
     - Identify related wallets on BUILD only ("Who else" in step 2).
  3. Run an event study of the latent's changes against every available
     series. A match means you have found the dimension, or a proxy for it.
     A fit without that event study closes nothing.
- **Quantify** the share of decisions the dimension would have to explain,
  and the evidence that it is the right one.

A wall claim must include the dimension inventory, with every missing
dimension handled in one of these ways.

**Information sources checked from this laptop on 2026-11-01.**

- **Work**:
  - Telegram public channel previews (`https://t.me/s/<channel>`): HTML with
    a timestamp on each post; page back with `?before=<post id>`.
  - Reddit RSS (`https://www.reddit.com/r/<sub>/new/.rss`, Atom).
    `old.reddit.com` redirects to a login page with HTTP 200, so check the
    content type, not only the status.
  - Bluesky public author feeds
    (`public.api.bsky.app/xrpc/app.bsky.feed.getAuthorFeed`).
  - Mastodon tag timelines (`mastodon.social/api/v1/timelines/tag/<tag>`).
    The global public timeline needs an account.
  - The GDELT DOC 2.0 API: `startdatetime`/`enddatetime` within a rolling
    3-month window, at 15-minute resolution. At most one request every 5 s,
    or it returns 429.
  - Google News RSS search, and the CoinDesk and Bloomberg markets RSS.
  - Federal Reserve press RSS, and YouTube channel RSS.
  - Wikimedia EventStreams (live edits), and the Hacker News API.
  - Polymarket's Gamma `/comments`, with `parent_entity_type` and
    `parent_entity_id` (422 without them). Comments on sealed units are
    sealed.
  - The alternative.me Fear & Greed index, and CoinGecko.
- **Blocked**:
  - X (Nitter returns no posts);
  - the Reddit JSON API and Bluesky search (403);
  - BLS RSS (403);
  - CryptoPanic (403).
- **Caveat**: most RSS and preview feeds hold only recent items, so record
  them live for future development blocks. Verify any source before relying
  on it, and log the request in `NOTES.md`.

## The direction catalog: try every item or rule it out with evidence

Track every item below in `state.json` as
`catalog: {<id>: {status: tried|ruled_out|not_applicable|infeasible|open, evidence}}`.
"Ruled out" needs a measurement, not an argument. "Infeasible" needs the
failing request and its response (e.g. HTTP 401), and a note of what you
used instead. Add every panel and audit proposal as its own item (X1, X2,
...; with its source) and close it like the others. Verify every endpoint
before you rely on it, and record what you found in `NOTES.md`.

Known on 2026-10-31 (checked from this laptop):

- **Work:** Binance spot and USD-M futures aggTrades archives; Binance, Bybit,
  Coinbase and Deribit REST and websockets; Bybit trading archives;
  Polymarket's CLOB market websocket; the RTDS Chainlink topics; the sports
  websocket.
- **Blocked:**
  - Pyth Hermes and Benchmarks (401, need a key);
  - Polymarket's PolyBolt socket (needs CLOB credentials, which you must not
    create);
  - data.chain.link stream history (429; unverified);
  - Binance futures bookTicker archive (404);
  - Tardis beyond its free first-of-month samples;
  - GRID esports (signup);
  - sportsbook and Betfair APIs (keys);
  - the X API (paid);
  - HLTV (Cloudflare).

**A. Where does the information come from?** For each candidate feed, run an
event study (the wallet's order or fill rate around the feed's moves, at lags
from under a second to minutes) and a lead-lag analysis against the wallet's
**order signing times** (B1), not its fill times. Then check whether adding
the feed to the rule closes the gap.

- A1 **The settlement source.**
  - Crypto Up/Down markets settle on Chainlink's 60-second TWAP data stream.
    Gamma `resolutionSource` is `data.chain.link/streams/btc-usd-twap-60s-streams`,
    and `cryptoMarketConfig` is `{twapEnabled, twapLookbackSeconds: 60}`. Neither
    Binance nor the slower on-chain Polygon aggregator settles them.
  - Historically, window k's settlement is window k+1's `priceToBeat`
    (5-minute resolution, finer with overlapping 15m, 1h and 4h windows).
    The Polygon resolution transactions may also carry the signed reports.
  - Live: the recorder's `rtds` feed has the 1-s Chainlink price and the 1-s
    60-s TWAP. Check which topic matches settlement against `priceToBeat`.
  - B3b, the last-60-second lock-in: inside the final minute part of the
    settlement value is already observed. Does the bot's activity or side
    change with it?
- A2 **Other spot venues** at millisecond resolution: Binance aggTrades
  archives (about 20 MB a day for BTCUSDT; each day is published early the
  next morning UTC), Coinbase, OKX, Bybit, Kraken. Also composite and
  volume-weighted prices.
- A3 **Derivatives**:
  - perpetual futures trades (Binance `data/futures/um/` archives, published
    later in the morning than spot) and order books (Bybit archives: pull
    single hours and reduce them at once);
  - funding and liquidations;
  - options (Deribit public API).
- A4 **Cross-asset and cross-market**:
  - ETH, SOL and XRP moves;
  - Polymarket's other markets on the same underlying (overlapping 15m, 1h and
    4h windows, the opposite outcome, related game lines);
  - A4b other venues' prices for the same question: Kalshi (crypto 15m and
    hourly, FOMC, sports) and Polymarket Perps.
- A5 **Sports and esports feeds faster or richer than ESPN**:
  - A5a Polymarket's own sports websocket (`wss://sports-api.polymarket.com/ws`,
    no auth: scores, periods, CS2 and Valorant maps, soccer minutes). It is in
    the recorder's `sports` feed; measure its latency against ESPN and against
    the wallet's order signing times, and map `gameId` to Gamma events;
  - league feeds: MLB statsapi live game feed (pitch-level timestamps), NHL
    api-web play-by-play, NBA cdn liveData play-by-play;
  - bo3.gg and liquipedia for CS2; stream delay.
- A6 **News, social and official calendars** for event markets (Fed
  statements, data releases, press wires), with their publication
  timestamps. A6b: CME FedWatch and fed funds futures for FOMC markets.
- A7 **Polymarket's own data**:
  - the CLOB `prices-history` endpoint and the recorded books (`clob_*`);
  - last trade and spread; the sums of the Up and Down (or YES and NO) asks
    and bids;
  - changes in volume and open interest;
  - fee and rebate parameters per market (Gamma `feeSchedule`, e.g. rate
    0.07, takerOnly, rebateRate 0.2; `makerRebatesFeeShareBps`).
- A8 **Operational events**: matching-engine restarts (after a restart the
  engine is post-only for two minutes), tick-size changes, API outages and
  pauses (e.g. the 1-hour pause on 2026-10-29). These are candidate causes of
  day-to-day activity swings.

**B. Mechanics and on-chain forensics**

- B1 **Full order reconstruction from V2 calldata.** This is the most
  decisive data in the study. Do it first for btc5m-bot, directional-maker,
  rn1-inplay-maker and tommy-cs2-maker.
  - The V2 exchanges' `matchOrders` (selector `0x3c2b4399`) is
    `matchOrders(bytes32 conditionId, Order takerOrder, Order[] makerOrders,
    uint256 takerFillAmount, uint256[] makerFillAmounts, uint256
    takerFeeAmount, uint256[] makerFeeAmounts)`.
  - The order struct is `Order(uint256 salt, address maker, address signer,
    uint256 tokenId, uint256 makerAmount, uint256 takerAmount, uint8 side,
    uint8 signatureType, uint256 timestamp, bytes32 metadata, bytes32
    builder, bytes signature)`.
  - `timestamp` is the millisecond signing time set by the client. Check
    that it is not after the block time. It gives the exact decision time of
    every filled order: lead-lag against every feed at millisecond
    resolution, resting lifetime (signing to fill) and requote cadence. A
    reviewer decoded tx
    `0xc1d69403280ccc313bb8e0561c49b5f35bb61c8eee5074935247719bdcd6cec8`: a
    btc5m-bot maker BUY of 30 at 0.20, signed 9.2 s before its block.
  - V2 orders have no expiration, nonce, taker or fee-rate fields. Older V1
    orders (`fillOrder` / `matchOrders` on the V1 exchanges) carry salt,
    maker, signer, taker, tokenId, makerAmount, takerAmount, expiration,
    nonce, feeRateBps, side, signatureType and signature.
  - The calldata gives each order's full original size and limit price.
  - Use `eth_getTransactionByHash` in batched JSON-RPC calls. Keep only the
    decoded fields, as parquet in `.cache/re/<key>/`, not raw inputs (about
    2.7 KB per transaction). Sample if there are more than about 100k
    transactions.
- B2 **Resting orders**: lifetimes, ladders, requote cadence, partial fills
  per order hash. Infer cancellations from orders that stop filling while the
  price trades through them, and from the recorded books.
- B3 **Inverse-fit the quote.** Fit the wallet's order prices as a fair value
  plus a spread. Try candidate fair-value models:
  - a digital option under realized volatility, with or without drift;
  - priced off the settlement feed or off Binance;
  - as a function of time left.
  Keep the model whose residuals are smallest and least structured.
- B4 **Complement and set mechanics**: buying both outcomes below 1 and
  merging; splits, conversions and redemptions (data-api activity types and
  the CTF contract events); negRisk conversions.
- B5 **Inventory and risk**: position caps, rebalancing toward flat pairs,
  behaviour after losses or drawdowns, daily caps, exposure across markets.
- B6 **Rebates**: does its volume or quoting target maker rebates (the
  per-market rebate pool) or taker rebate tiers?
- B7 **Liquidity rewards**: the share of its orders with size of at least
  `rewardsMinSize` and price within `rewardsMaxSpread` of the midpoint
  (BTC 5m: 50 shares and 4.5 cents), and REWARD rows per market.
- B8 **Holding rewards** (`holdingRewardsEnabled`) as a reason to park
  capital or pick markets.
- B9 **Maker rebate pool share** by market: does it pick markets with high
  taker fees and few competing makers?

**C. Who and what else**

- C1 **Sibling wallets**:
  - common funding addresses and shared transactions;
  - in V2, `signatureType` 3 has signer = maker, so recover the owner key from
    the wrapped signature or the wallet contract (Safe `getOwners`);
  - their combined behaviour.
- C2 **Copy or follow trading**: lead-lag between the wallet's orders and
  every other large wallet in the same markets. Test the strong form too:
  same token and side, a fixed size ratio, a lag of 0-30 s.
- C3 **Counterparties**: who it trades against (the same few takers, retail,
  other bots), and whether its edge is their predictable flow.
- C4 **Bot versions**: change-point detection over its whole history (sizes,
  prices, markets, timing). Decode each version separately instead of pooling
  them. C4b: match change points against Polymarket announcements (fees,
  rewards, rebates, listings), e.g. tommy-cs2-maker's switch to making on
  10-16/17.
- C5 **Human or scheduled activity**: hours of the day, days of the week,
  reaction delays consistent with a person, scheduled jobs.
- C6 **Combos and RFQ** (Gamma `rfqEnabled`): hedging or making for combo
  flow.
- C7 **Self-matching and referrals**: trades against its own or related
  wallets, circular volume, referral income.
- C8 **Fingerprinting the bot software**:
  - the salt distribution (`round(random * Date.now())` points to the
    TypeScript client);
  - `builder` and `metadata` codes;
  - fixed order sizes.
  Search public GitHub Polymarket bots with matching defaults and test their
  default rules against the wallet. One btc5m-bot wallet is named
  "dangerously-skip-permissions", a Claude Code flag.

**D. Targets and models**

- D1 **The right unit of decision**: per order (B1) rather than per fill or
  per time bin; per market for selection; per event for triggers.
- D2 **Model classes beyond gradient boosting on bins**:
  - hazard or survival models for when it acts;
  - a state machine or HMM over a window or game;
  - symbolic or tree-distilled rules;
  - sequence models.
- D3 **Replay**: simulate a candidate bot order by order against the tape and
  the recorded books, and compare it with the wallet decision by decision.
- D4 **Economics**: decompose its PnL by component (selection, timing, side,
  price, rebates, rewards, carry), and check that the decoded rule earns the
  same components.

**E. Hidden dimensions and indicators** (see the section of that name; open
for every strategy from 2026-11-01):

- E1 **Dimension inventory**: every family listed there in `state.json`
  `dimensions`, with a status, a source, a resolution and a verdict.
- E2 **Residual shape**: the unexplained share per component; when the
  residual falls; whether it leads the feeds; who else acts with it.
- E3 **Indicator screen per dimension family**: event definitions at several
  horizons, pre-registered, with BH on BUILD and confirmation on VALIDATE,
  plus a timing, direction and incremental test for each.
- E4 **Discrepancy and composite indicators** between dimensions.
- E5 **Information dimensions**: news, social and official sources (see the
  sources checked on 2026-11-01), screened against selection and timing
  even for crypto bots (which windows or days it skips), and recorded live
  where only recent items are available.
- E6 **Latent-dimension inference**: a fitted hidden state, its
  incremental gain on VALIDATE over the co-occurrence and self-excitation
  baselines, and its event study against every available series.
- E7 **Residual synchrony across markets**: `residual_clustering` (with
  `period_s` for scheduled markets; p <= 0.01 and a ratio of at least 1.5),
  with the top clusters looked up in news, social and status archives.

## Data: expand it (the earlier studies used too little)

The HTTP cache `.cache/http.sqlite` is shared and safe for concurrent use. Go
through the polyrea adapters so every fetch is cached, and fetch politely
(the clients rate-limit per host). Useful sources besides the catalog:

- **Wallet record**:
  - `PolymarketData().activity(wallet, start, end)` back to its first trade
    (cursor paging, cached). Activity types include TRADE, SPLIT, MERGE,
    REDEEM, REWARD, CONVERSION, MAKER_REBATE and YIELD.
  - `/v2/user-pnl` daily series; `/positions`; `/value`.
  - `polyrea.workflows.investigate.load_window` builds a ledger.
- **Every market the wallet traded** in your development period, not a
  sample:
  - Gamma metadata (`markets_by_condition`);
  - full tapes from data-api `/trades`
    (`PolymarketData().market_trades(cid, start, end, taker_only=...)`).
    Taker rows are aggressive orders and the rest are maker rows. Snap tape
    prices with `polyrea.analysis.updown.snap_price`;
  - a matched set of markets it did not trade, to learn what it avoids.
- **Live recordings**: `tools/live.py` `iter_live` (development blocks
  only); see "The live lab".
- **On-chain fills** (powerful for makers): Polygon `eth_getLogs` for
  `OrderFilled` on the CTF exchanges, filtered by topic2 = maker (the wallet,
  32-byte padded) or topic3 = taker.
  - In the study period fills come from the V2 exchanges
    `0xe111180000d2663c0091e4f400237545b87b996b` and
    `0xe2222d279d744050d28e00520010520000310f59` (both verified in cached
    receipts).
  - V2 topic0 is
    `0xd543adfd945773f1a62f74f0ee55a5e3b9b1a28262980ba90b1a89f2ea84d8ee`;
    topics [orderHash, maker, taker]; data [side, tokenId,
    makerAmountFilled, takerAmountFilled, fee, ...]; side 0 = BUY.
  - Older history used the V1 exchanges: topic0
    `0xd0a08e8c493f9c94f29311604c9de1b4e8c8d4c06bd0c789af57f2d65bfec0f6`,
    data [makerAssetId, takerAssetId, makerAmountFilled, takerAmountFilled,
    fee]. Verify the V1 addresses from a receipt before filtering on them.
  - `polyrea/adapters/chain.py` (`decode_fills`) decodes both.
  - Grouping a wallet's maker fills by `orderHash` reconstructs each resting
    order. The calldata (catalog B1) adds what the logs lack, including the
    signing time.
  - Get block timestamps via `eth_getBlockByNumber` and cache them.
  - RPC: `https://polygon.drpc.org` through `HttpClient.post_json`. Keep each
    call to a few thousand blocks; drpc rate-limits.
- **Reference prices**:
  - `polyrea.adapters.spot.binance_seconds` (1-s klines);
  - Binance aggTrades archives with millisecond timestamps
    (`https://data.binance.vision/data/spot/daily/aggTrades/BTCUSDT/BTCUSDT-aggTrades-YYYY-MM-DD.zip`,
    SHA-256 in `.CHECKSUM`);
  - Kraken trades, and Coinbase/OKX candles (registered external sources in
    `polyrea/pit.py`);
  - the settlement feeds in catalog A1.
- **Sports and esports**: `polyrea.adapters.espn` (play-by-play with wall
  clocks, win probability, soccer key events), plus the feeds in catalog A5.
- **Events**: FOMC calendar, deadline markets via Gamma.

Put large intermediate data in `.cache/re/<your key>/` (git-ignored), not in
the research folder.

## Tools you can reuse (read the code)

- `polyrea/analysis/updown.py`, the Up/Down window model:
  - `windows_from_markets`;
  - `fair_up_vectorized` with the pre-window TWAP strike;
  - `SpotIndex`;
  - score functions;
  - `match_test` (rotation null, two stratifications, effect size,
    `tape_momentum_sign` control);
  - `maker_buy_prints`, `taker_flow`;
  - taker and maker backtests (`backtest`, `maker_backtest`,
    `spot_reactive_maker_backtest` with `match_slack`,
    `fixed_price_ladder_backtest`);
  - `quote_price` (dynamic tick).
- `polyrea/workflows/updown_study.py`: `sample_blocks`, `all_blocks`,
  `load_period` / `_load_period`, `run_frozen_rule_extension`.
- Also:
  - `polyrea/workflows/sports_study.py`;
  - `polyrea/workflows/maker_study.py`;
  - `polyrea/analysis/tape_maker.py`;
  - `polyrea/analysis/profile.py`;
  - `polyrea/analysis/ledger.py`;
  - `polyrea/analysis/rebates.py`;
  - `polyrea/pit.py` (point-in-time store and guarded view);
  - `polyrea/stats/`.
- `research/reverse_engineering/tools/indicators.py` (read its docstring;
  `python .../indicators.py selftest`):
  - causal grids and transforms (`grid`, `asof`, `counts`, `ewm`, `zscore`,
    `jump_z`);
  - event detectors (`jumps`, `crossings`, `cusum`, `divergence`, `burst`,
    `first_occurrence`), with `gate`, `compound` and `event_features`;
  - `event_study`, with an activity-stratified swap null (falling back to
    length classes, then a within-unit jitter), level and shape tests over
    windows of 1-16 lag bins, and a signed version for side;
  - `screen`, with BH q-values over one joint family;
  - `incremental_auc` over a base score with a block bootstrap;
  - `residual_clustering`;
  - `ledger_row`.
- Python packages: numpy, pandas, scipy, statsmodels, scikit-learn, lightgbm,
  pyarrow, websockets, httpx (`pip install -e '.[test,research]'`; already
  installed in `.venv`). Interpreter: `.venv/Scripts/python.exe` on Windows
  (`.venv/bin/python` on Linux/macOS), run from the repository root.

## How to work

1. Read your dossier and, if continuing, `NOTES.md`, `state.json`,
   `FINAL_RULE.md`, the panel files in `panels/` and any `EXAM*.md` and
   `results/wall_audit_*.json`.
2. Write the five-or-more competing explanations (see the premise). Each
   names the dimensions it needs and their status in `dimensions`, and at
   least one rests on a missing or blocked dimension. Pick what this
   iteration will discriminate between.
3. Expand the data and measure what you could not see before. Update the
   dimension inventory and read the residual's shape ("Hidden dimensions
   and indicators", steps 1-2). Pick the dimensions it points to, and build
   and test indicators from them (steps 3-4).
4. Describe the behaviour precisely, component by component: per market and
   per second, what the wallet does (orders, fills, sides, prices relative to
   the touch and to fair value, sizes and lifetimes, inventory paths, timing
   relative to every feed and to game events), and what it avoids.
5. Behaviour cloning is a tool for discovering signals, not the goal. Use it
   to find which inputs matter (report feature importances), then distill
   them into an explicit, mechanistic rule per component.
6. Test explicit rules against the wallet on VALIDATE, and keep a ledger of
   every hypothesis (family, description, validation metrics, verdict).
7. Work through the catalog and the panel's proposals. If two iterations
   bring less than 0.01 on your primary metric, the next one must pivot to a
   different paradigm.

## Accuracy: what to measure (on VALIDATE while developing; the examiner on sealed data)

Report every metric per wallet as well as pooled when the strategy has
several wallets.

- **Selection**: does the rule pick out the wallet's trades among all
  comparable trades? For crypto Up/Down use `match_test` (stratified AUC
  against the rotation null, recall and lift at the pre-registered
  threshold). For sports and events use a timeline-shift or
  market-permutation null.
- **Behaviour cloning**:
  - (a) presence: AUC of predicting whether the wallet is filled or trades in
    each (market, time bin), or better, whether it has an order resting;
  - (b) side: accuracy of the side it takes given that it acts, against the
    best market-only baseline (e.g. "buy the favourite");
  - (c) price: share of its fills (or orders) whose price the rule predicts
    within one tick.
- **Outcome**:
  - correlation between the rule's per-market (or per-window) PnL and the
    wallet's;
  - the rule's held-out return under strict fills, latency >= 2 s and, for
    makers, `match_slack=2`, against the wallet's own return on the same
    markets.
- **Co-occurrence baseline** (required with every presence or selection
  metric):
  - The same model or rule restricted to market activity alone: other
    traders' prints and their timing in the previous seconds, time in the
    window or game, price level. No reference feed, no event feed.
  - A wallet that races other traders on the same trigger is "predicted" by
    their prints without its rule being decoded.
  - Report the metric, the baseline and the gain over the baseline.
  - The wallet's own prints, and prints in transactions where it was the
    maker, are never part of any feature.

**High accuracy target** (the user's definition, pre-registered on
2026-10-31; judged by the examiner on the exam lot, point-in-time):

1. **Scope.** The rule's universe covers at least 80% of the wallets' fills in
   the lot and at least 80% of their absolute PnL. Metrics conditioned on an
   oracle, a subset of bot versions or wallets, or the wallet's own presence
   are reported but never count toward the target.
2. **Presence or selection.**
   - Presence AUC >= 0.85 without own-state features, or selection AUC >= 0.80
     with recall >= 50% at lift >= 3.
   - In both cases the gain over the stronger of two market-activity
     baselines must be at least 0.05 AUC. One baseline is yours; the other is
     fitted by the examiner, with the same model class, tuning budget and
     BUILD data. The lower bound of the gain's 95% block-bootstrap interval
     (2-hour blocks, or games) must be above 0.
3. **Side** (where the examiner finds the wallet chooses one: one-sided in at
   least 20% of its windows or markets). Accuracy >= 80%, reported against the
   market-only and the own-inventory-only baselines. A side rule that is just
   one of those baselines is a valid description, but it must say so.
4. **Price** (for makers; also for takers' limit prices). Within one tick for
   >= 80% of orders (or fills), reported against the best trivial anchor (last
   print, touch, touch minus a tick), under the same proviso.
5. **Outcome.** The per-market correlation between the executable rule's
   realized PnL (strict fills, not an expectation) and the wallet's is >= 0.5,
   in both Pearson and Spearman.
6. **Significance.** Every test above (the presence or selection gain over
   its baseline; a rotation or permutation null with at least 2,000 draws) is
   one-sided at alpha = 0.0025, which spreads 0.01 over up to 4 exam rounds.
   Blocks are 2-hour blocks or games.
7. **Replication.** The examiner splits the lot into an earlier and a later
   half from listing metadata, before reading any fills. On each half, and for
   each wallet with at least 300 fills or 30 markets in the lot, every
   threshold in 2-5 holds within 0.03 (AUC, correlation) or 3 points
   (accuracy).

While developing, report the same metrics on VALIDATE, using the named keys
in `state.json` `target_metrics` (see "Files"). Claim the target only when
every condition holds there. Report every metric even when the target is not
met.

## The wall (only on proof)

- **Budget**: up to about 20 hours of work per strategy, in iterations of
  about 100 minutes that each end with a checkpoint. Running out of budget
  without decoding the strategy is recorded as a failure, not as a wall.
- **No diminishing-returns stop.** If two iterations bring less than 0.01 on
  your primary metric, the next iteration must pivot to a different paradigm
  (a target, data source, unit of decision or model class from the catalog
  or the panel). Tuning the same model is not a pivot.
- **Claiming a wall.** You may claim one only if all of these hold:
  - you have worked at least 10 hours on the strategy;
  - every catalog item, including every panel and audit proposal (X items),
    is `tried`, `ruled_out`, `not_applicable` or `infeasible`, with evidence;
  - the dimension inventory (E1) is complete, and every missing or blocked
    dimension has been fetched, proxied, recorded live or inferred (E6), or
    closed as `infeasible` as step 1 of that section defines it, with its
    indicator results in the `indicators` ledger;
  - no dimension has verdict `untested`: every `have` and `proxy` dimension
    has had its pre-registered family screened, and every `no_effect`
    carries its `min_detectable_share`;
  - you show quantitatively where the unexplained part of the decisions
    comes from. For example: the wallet's decisions precede every public feed
    you obtained (by how much, and how often); or the remaining decisions are
    statistically indistinguishable from random given every state variable
    you measured.
- **Audit.** Three independent auditors then try to name concrete untried
  directions. The wall stands only if none of them can. Otherwise their
  directions become your next to-do list and you continue.
- **Target.** When you meet the high-accuracy target on VALIDATE, the
  examiner checks the sealed data. If its match verdict is not "pass", you
  continue from its diagnosis.

## Engineering rules (other agents share the machine)

### Local run (2026-10-31 onward): a shared Windows laptop

The run happens on the user's own computer: Windows 11, 8 cores, 12.9 GB of
RAM shared with the user's desktop and two other agents (often only 1-3 GB
free), about 15 GB of free disk, one home internet connection.

- **Shell**: the Bash tool is Git Bash (`date -u +%s`, pipes and heredocs
  work). Use forward-slash paths from the repository root. Interpreter:
  `.venv/Scripts/python.exe`. Never use `pkill -f`. Stop your own background
  job through the tool that started it, or with `taskkill //PID <pid> //F`.
- **Memory**:
  - Before every heavy job (model training, a join over millions of rows, a
    large parquet read) run
    `.venv/Scripts/python.exe research/reverse_engineering/tools/resources.py --wait-mem 1200`.
  - Keep each process under about 1 GB: stream per market, window or day;
    read only the parquet columns you need; use float32 and categoricals;
    train LightGBM on subsamples (negatives can be subsampled with weights)
    with `max_bin` <= 63; free frames you no longer need.
  - If a job dies (MemoryError, silent kill), shrink it; do not retry it
    unchanged.
- **Disk**:
  - Keep `.cache/re/<your key>/` under 1.5 GB.
  - Before a large fetch run `resources.py --need-disk 5000`. If it reports
    low disk, do not download more.
  - Big archives (e.g. Binance aggTrades zips, about 20 MB a day) are not worth
    keeping in the shared HTTP cache. Download them with `httpx` into
    `.cache/re/<your key>/`, verify the `.CHECKSUM`, reduce them at once (for
    example to per-100 ms or per-second parquet for the hours you need), and
    delete the zip.
- **The live recorder** (`tools/live.py`) runs for the whole study. Never
  stop or restart it. Check it with
  `.venv/Scripts/python.exe research/reverse_engineering/tools/live.py status`.
  If it is not running, say so in `NOTES.md` and in your return; do not start
  a second one.
- **Network**: all agents share one connection and the per-host rate limits
  of the polyrea `HttpClient`. drpc may throttle (back off on 429). Prefer
  narrow fetches (the wallet's own markets and windows, matched controls)
  over bulk downloads.
- **Data from the earlier cloud run is gone**:
  - `NOTES.md` may refer to intermediates in `.cache/re/<key>/` (and an HTTP
    cache) that were left on the cloud machine. Re-fetch what you need and
    skip what you no longer need.
  - Code written there may hold Linux paths
    (`/home/user/PolymarketResearchAgent/...`). Make them relative to the
    repository root.
- **Interrupted work**: the run was restarted on 2026-10-31 around 11:30 UTC
  with this brief. Code and result files from an interrupted iteration may
  sit in `code/` without a matching entry in `NOTES.md`. Check them before
  redoing the work.
- **Your workspace**:
  - Stream per market or per window; store intermediates as parquet.
  - Write only inside `research/reverse_engineering/<your key>/` (code, small
    results, notes) and `.cache/re/<your key>/` (large data).
  - Do not modify `polyrea/`, other folders or other agents' files. If you
    find a bug in polyrea, write it in `NOTES.md` and report it in your
    return.
  - No git commands.
  - Delete large intermediates you no longer need.
- Keep tool output short (summaries, not dumps), and write findings into
  `NOTES.md` as you go, so a successor can continue from it.

## Files you maintain (in `research/reverse_engineering/<your key>/`)

- **`NOTES.md`**, the lab notebook: data gathered, competing explanations,
  hypotheses, evidence, metrics, decisions, open questions, what to try next.
  It also holds a "Missing dimensions" section (the residual's shape, and the
  dimensions it points to) and the pre-registration of each indicator screen.
- **`state.json`** holds:
  - `primary_metric`;
  - `status`: continue | target_reached | wall, plus `wall_reason`;
  - `sealed_from` (copied from your prompt) and `live_lab`;
  - `strategy_statement`: a plain-language description of what the bot
    does, updated every iteration;
  - `components` and `catalog`, as above;
  - `target_metrics`: your best rule's VALIDATE values under these exact keys
    (null where not applicable): `presence_auc`, `selection_auc`,
    `selection_recall`, `selection_lift`, `presence_baseline` and
    `selection_baseline` (the activity-only baselines for those metrics),
    `side_accuracy`,
    `side_baseline`, `price_within_tick`, `pnl_corr_pearson`,
    `pnl_corr_spearman`, `coverage_fills`, `coverage_abs_pnl`;
  - `best: {rule_id, validate_metrics}`;
  - `hypotheses: [{id, family, description, validate_metrics, verdict}]`;
  - `data_sources: [...]`;
  - `dimensions: {<name>: {family, status, source, resolution, publication_latency, best_indicator, min_detectable_share, verdict}}`
    (E1);
  - `indicators: [...]`: every indicator tried, with its dimension,
    definition, event definition, period (BUILD, VALIDATE or legacy),
    result (lags, lifts, `p_level`, `p_shape`, `p_link`, q, incremental gain
    and interval) and verdict (`ledger_row`, which keeps legacy results
    whole);
  - `iterations: [{n, minutes, best_validate_score, families}]`. Append one
    entry per iteration.
- **`FINAL_RULE.md`** and **`code/final_rule.py`**: the best rule so far,
  frozen, with all parameters constants.
  - `FINAL_RULE.md` describes the rule component by component, tagging each
    as exam-verified, VALIDATE-only or hypothesis, and keeps two
    short sections the user cares most about:
    - **Why it works**: the economic mechanism. Who loses to this strategy
      and why, and what it is paid for (information, speed, liquidity
      provision, rebates, rewards, carry).
    - **Can a normal user deploy it now**: what it depends on (latency, data
      feeds, rebate tier, capital, market listings and Polymarket policy);
      whether those conditions still hold in the latest development data;
      what a replicator with a normal connection and computer would earn.
  - `final_rule.py` must expose `evaluate(start_ts, end_ts, intervals=None) -> dict`
    (with `intervals`, a list of `[a, b)` pairs, only units starting in them count). It
    loads the data it needs for that period, applies the frozen rule
    point-in-time, and returns the metrics above (selection, behaviour
    cloning, outcome; per wallet and pooled), so the examiner can run it on
    sealed data without editing it. Live-recording inputs come through
    `iter_live(..., allow_sealed=ALLOW_SEALED)` with a module-level
    `ALLOW_SEALED = False` that only the examiner's driver sets to True.

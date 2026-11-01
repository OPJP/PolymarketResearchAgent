# Panel, iteration 15: information source and data (fresh eyes)

Lens: what the operator sees, earlier or better, that the investigation has not obtained, and which data would most
sharply separate the leading explanations (R: round results seen early; K: an in-round kill / bomb state; and the
vendor's identity). Written 2026-11-01, 14:17-14:50 UTC, inside the sealed block 12-18. Nothing in `.cache/live/sealed/`
was opened and no live recording was read. Every market, fill and listing I touched belongs to 16-22 Oct (before H).
External probes were HEAD requests or documentation pages only. They covered no data file and no sealed date:
- the hours probed for an orderbook archive are all before H;
- the one bo3 game read is 2026-10-16.

## What I read and what I ran

Read: BRIEF.md (premise, hidden dimensions, catalog, accuracy targets); NOTES.md iterations 14-15 in full, earlier
iterations by section; state.json (catalog A1-X218 and E1-E7 with evidence, components, the 39 `dimensions`, live_lab);
FINAL_RULE.md by section; panels/iter14_information.md. No EXAM or wall-audit files exist.

Scripts and outputs (scratchpad, not the workspace):
`C:/Users/REMOTE~1/AppData/Local/Temp/claude/C--Dev-trading-research-PolymarketResearchAgent/97f207f2-bd1a-4cdb-a63d-2290c58d22c3/scratchpad/iter15info/`.
Each process stayed far under 300 MB, and `resources.py --wait-mem 600` ran first.
- `mode2_check.py`, `mode2_by_taker.py`, `mode2_price.py`: the ~1-s lag mode of its filled maker orders after
  wallet-free group-P takes, split by its own take, by taker, and by price.
- `visibility_by_dv.py`: share of its V-changes with a visible group-P take, by move size.
- `vendor_mux.py`: cross-event, cross-subscriber coincidences (does the vendor serialize events on one stream?).
- Inline checks: builder / metadata codes in `calldata_all.parquet`; group-P takes before the scheduled start;
  eventMetadata keys against the traded label.
- Web, as a plain visitor:
  - PMXT archive host probes (HEAD only);
  - Telonex pricing and docs pages;
  - the PMXT ingestion READMEs on GitHub;
  - bo3 `/games/190260/rounds` (a 10-16 game).

## Critique: what the investigation is missing or getting wrong

### 1. "No books before 10-31" was treated as fixed, but historical tick-level Polymarket book data are sold

Since iteration 2 (X18), every book-level question has had to wait for the live lab:
- the uncensored ladder;
- cancel waves;
- others' best bid;
- the round-market books.

The live lab has about 3 hours of wallet units (BUILD-live, 10-31). VALIDATE-live has none: the wallet made 0 trades in
11-01 06-12, and the next development block starts after the budget ends. Historical archives of Polymarket's CLOB
market websocket exist, and nobody checked them:

- **PMXT, the free archive.** It publishes hourly Parquet dumps of the market channel, with these columns: `timestamp`
  (server), `timestamp_received`, `event_type` (book / price_change / last_trade_price / tick_size_change), market,
  asset, price, size, side, best bid and ask, and the tx hash. I checked it with HEAD requests only.
  - `r2v2.pmxt.dev/polymarket_orderbook_2026-08-08T18.parquet` exists (556 MB, `Accept-Ranges: bytes`). So do
    08-08T00 / T23 and 08-09T00 / T06 / T12.
  - Every hour probed from 08-10 to 10-21 returns 404, including dense 3-hour steps on 09-10, 10-16 and 10-20.
  - v1 (`r2.pmxt.dev`) ends earlier: 2026-04-06T23 exists (785 MB); May to October return 404.
  - The listing host `archive.pmxt.dev` timed out on TCP connect (ports 443 and 80) at 14:2x UTC.
  - **The free archive does not cover the development period.**
- **Telonex, commercial.** Its Polymarket channels are trades, quotes, `book_snapshot_5` / `_25` / `_full` and
  `onchain_fills`, delivered as daily Parquet files per market. The plans are a free trial ($0, an account with an API
  key, 5 file downloads in total) and $99 a month for one exchange with unlimited downloads. October coverage of the
  CS2 markets and the snapshot cadence of `book_snapshot_full` are not verified. That needs its availability endpoint
  or a key.

This is proposal P2.

### 2. Under the brief's point-in-time rules, only the vendor's live message stream can carry the price item

X201 measured the lag tolerance of the price item:

| Input | Set unit | V-change bursts (90% of filled orders) |
| --- | --- | --- |
| V lagged 0.25 s | 0.355 | |
| V lagged 4 s | 0.293 | 0.20-0.23 |
| Oracle (V at t) | 0.875 | |

The brief admits a public game event only with a publication delay. ESPN plays, for example, enter at wall clock plus
at least 5 s. So:
- demos, the stream, HLTV, Valve's 4-s Dota snapshots and bo3 can decode V's *function*, which is what R vs K is
  about;
- none of them can carry the examined price item, and neither can a vendor's historical `ts` if that field is game
  time rather than send time;
- only the vendor's messages stamped at receipt can, which means a live recording with the user's token (P1).

The asks to the user should be ranked on that basis, not listed side by side. Two further points:
- The outcome item is capped even with the feed. The executable rule must act with a latency of at least 2 s, and an
  oracle copy of the wallet's own decisions at 2 s reaches only 0.43 / 0.40 (X155). The auditors should hear this as a
  measured clause, not as a data gap.
- No new information source changes the selection item. It already passes on VALIDATE (0.970, recall 0.744 at lift
  3.155).

### 3. The visible-message proxy saturates, so the take clocks cannot type the messages

Share of its V-changes with a wallet-free group-P take on the event in the 3 s before (`visibility_by_dv.json`).
Filled bursts only (censored), 17,024 V-changes in 16-22 Oct. The null is the same test 60 s earlier.

| \|dV\| | 0-1c | 1-2c | 2-3c | 3-5c | 5-8c | 8-15c | > 15c |
| --- | --- | --- | --- | --- | --- | --- | --- |
| n | 6,264 | 2,295 | 1,571 | 2,427 | 2,032 | 1,683 | 752 |
| Excess over null | 5.6% | 9.1% | 12.8% | 14.5% | 22.5% | 24.2% | 21.8% |

So the "dark" 85% is not a fee or spread threshold on small messages. Even moves of 5c or more are 75% dark: the
co-subscribers' takes are liquidity-limited, since a stale ask must exist for them to take. Two consequences:
- any R-vs-K statistic built on the informed-take clocks samples the large, takeable messages, which biases it toward
  R;
- labelling message types needs a denser witness: other makers' cancels and re-posts on the book (P2) or the vendor
  feed itself (P1).

### 4. Its ~1-s re-post spike is anchored to the message, not to a public match

I locked its filled maker bursts (first order per token, 50-ms chains) to the latest earlier wallet-free group-P taker
signature on the same event within 3 s. 2,920 bursts were locked (`mode2_check.json`).

- 636 fall in [1.0, 1.1) s, against 45-60 per 100-ms bin at 0.6-1.0 s and 150 in [1.1, 1.2) s.
- 554 of those 636 have no own take within ±150 ms of the informed signature, so the spike is not its take-then-repost
  cycle.
- The spike follows the fastest signer, not each taker's own match. Locked to P4e (0x4ebc2722) it is 597, and to RN1
  (0x2005d16a) 70. Locked to the slow trio, whose takes match at about sign + 2.0-2.2 s, the peak moves to +0.4-0.7 s
  (`mode2_by_taker.json`).

So it re-posts about 1.05 s after the feed's message, when the delayed FAKs land (secondsDelay = 1). It does not react
to the public print of a match. This is consistent with X26 (re-sign hazard 9.1x on the complement in [1,000, 1,140)
ms after takers that hit only others, 17x in the 1,040-ms bin) and with `maker_trade_latency.json` (3.4% of its
signings within 50 ms after a trade message, nearly all after its own fills).

Price: same-token spike orders sit within 1c of the informed take's executed price in 0.656 of cases (n 151), against
0.423 at lags of 1.5-3 s. Complement orders sit a median 3c under 1 - fill, i.e. on its pair constant of about 0.97
(n 410; `mode2_price.json`).

What this means:
- The design is built around Polymarket's taker-delay window. It pulls fast (11-19 ms after its own takes, X49) and
  re-posts once the window has passed.
- The earlier claim that an informed take is public only at its block is right for the historical tape. On the live
  websocket the take is public at its match, about 1 s earlier. The rule can use that legitimately (X29's match clock
  scores 0.353 against 0.305 for the block-time print), but historically only through an archive (P2).

### 5. The forward exam's recordings are partly conditioned on the wallet, and the own recorders stop on 11-03

- **`clob_wallets` is conditioned on the wallet.** By the brief's description it subscribes to the markets the studied
  wallets traded in the last 6 hours. A book feature taken from it exists only after the wallet has traded, which is a
  presence leak, and it misses each event's opening.
- **The wallet-independent recorders stop on 11-03.** `tommy_cs2_near` (all CS2 books in play) is wallet-independent,
  but it stops at 11-03 00:00. So do `tommy_dota_rt`, `tommy_tp_odds2`, `tommy_chat` and `tommy_kick_pdt`.
- **Dota is a large share of the forward fills.** CS2-only coverage of fills was 0.425-0.457 on 10-31 12-18 (X112).
  Valve state is the Dota half's only public in-game input, and its recorder stops with the others.

This is proposal P4.

### 6. Smaller measured points (so nobody redoes them)

- **Vendor architecture (cross-event serialization; `vendor_mux.py`).** I paired different subscribers' messages in
  different events. 6,954 group-P messages gave:

  | Gap (ms) | 0-5 | 5-20 | 20-50 | 50-100 | 100-200 |
  | --- | --- | --- | --- | --- | --- |
  | Observed | 1 | 2 | 3 | 5 | 15 |
  | Null (±31 / 47 s shifts) | 0.25 | 0.75 | 2.25 | 4.25 | 9.75 |

  The same-event control is 412-444x at 0-20 ms. There is no deficit at short gaps, so nothing points to one
  serialized vendor stream; per-match sockets, as PandaScore documents for LLF, fit. But concurrency in its markets is
  too low for power.
- **Volume.** The operator's non-GRID CS2 events of 16-22 Oct are 97: 77 for the wallet and 20 for 0x7d67f01d. That is
  about 14 a day, or about 5k a year for CS2 alone, against PandaScore's stated volume for LLF of about 10k matches a
  year over three titles. The order of magnitude fits; this is a rough check, not evidence.

## Proposals (ranked by the chance that they close the gap)

### P1. Record the vendor's push socket live, stamped at receipt (strong form of X206; the only point-in-time carrier of the price item)

- **Hypothesis.** The private value V is the operator's function of a vendor message stream; the leading candidate is
  PandaScore's Low Latency Feed. Recorded live with receive-time stamps, the messages:
  - become a legitimate rule input on every future block, which the examiner can score;
  - lock to its V-changes at a fixed lag of 0-100 ms;
  - type each message (kill, bomb, round_end, frames with alive counts and the timer), which settles R vs K at once.
- **Why it fits.**
  - Critique 2: no delayed source can carry the price item.
  - The fan-out is machine-timed, fixed-lag and stable per subscriber (event SD 7-9 ms, X97 / X111), with no deficit
    of cross-event coincidences (critique 6).
  - Titles: CS2 / Dota / LoL with fixed lags, and Valorant without them, matching LLF's title list (X206).
  - The listings are PandaScore objects (`pandascoreMatchId`, `serie`, `leagueTier`).
  - Coverage is per match, not per tournament (iteration-14 panel). The volume fits (critique 6).
  - X206 as written asks for the historical `/games/{id}/events` `ts`. That field is probably game-server time, and the
    examiner would have to delay it like ESPN plays, which X201 shows kills the price item.
- **Test (user-gated, in order of cost).**
  0. Run P3 first (key-free); it says whether LLF-type pre-game messages exist at all.
  1. **Free tier (user account).** Read `low_latency_feed` for the 384 development events. Pre-registered: the AUC of
     the flag against the operator-level label (wallet or 0x7d67f01d), over non-GRID events.
  2. **Real-time plan (user's decision; paid).** Write a recorder with `tools/live.py` `Writer` and unit filing
     (sealed-start units always sealed), a hard stop, at most 3 connections per match, under 100 MB of memory. It
     subscribes to every Polymarket non-GRID CS2 / Dota / LoL event in play, discovered through `/low_latency_feeds`
     within 15 min of start. Record it in `state.json` `live_lab`.
  3. **On development blocks.**
     - Run the event study of the operator accounts' V-change decisions (calldata sign ms) against the message `ts` /
       receive times, per message type, with the swap null.
     - Fit V = f(score, side, alive counts, bomb, timer, economy) on BUILD-live blocks and score within one tick on
       VALIDATE-live blocks.
     - Also measure the historical `ts` against the receive time, which shows whether the historical endpoint can ever
       be used point in time.
- **Data needed.** A PandaScore token from the user (the agent must not create accounts); calldata of the operator's
  development-block orders (fetched as now).
- **Signature if true.**
  - The flag has AUC ≥ 0.95 on non-GRID events, with every traded match flagged.
  - The share of V-changes within 0-150 ms after a message is ≥ 5x the null, with a lag SD ≤ 50 ms.
  - Under K, V moves at kill and bomb messages, not only at round_end.
  - V's within-one-tick share on V-change bursts rises from 0.20-0.23 to ≥ 0.6.
- **If false.** If the flag does not separate, or no lock appears: the vendor is not LLF. Then P3 and P2 are the next
  data, and the dimension `feed_vendor_identity` stays blocked with that response on file.

### P2. Historical tick-level Polymarket book for 16-22 Oct: uncensored V, a public message clock, match-time prints (new; Telonex; PMXT verified absent)

- **Hypothesis.** Most of what the iteration-15 R-vs-K findings lack is in Polymarket's own book on those days:
  - the wallet's uncensored ladder (every add and cancel of its 100-share whole-cent levels, not just filled burst
    tops);
  - the co-receiver makers' cancel and re-post waves at server ms, a dense, public, point-in-time witness of the dark
    messages (critique 3);
  - others' best bid J before signing;
  - match-time prints.

  With 7 days instead of 3 hours, the censoring and clock caveats on iteration-15 findings 7, 8 and 16-24 can be
  removed or quantified. J and the match-time print are also the best public price anchors:
  - J scores 0.499 on BUILD-live against 0.322 for the block-time print (X201, X43);
  - the match clock scores 0.353 against 0.305 (X29).
- **Why it fits.**
  - Critiques 1, 3 and 4.
  - Every pending live-only test waits for wallet units that will not come within the budget: X54, X115, X164, X197
    step 2, X212 and X47b.
  - If the vendor holds h1 / h2, the examiner can score book-anchored components on the historical lots, which X18 says
    is impossible today.
- **Test.**
  1. **Availability (the agent).** Use Telonex's markets dataset (documented as browsable without a key), or its
     availability endpoint if that answers without a key. Check 3 development CS2 map markets of 10-20 / 10-21, and
     the round handicap / totals markets of one event. Record the
     request and the response. Request development dates only (≤ 10-22 and development blocks after T0). Never fetch
     10-23..10-30 or a sealed block; whether those exist is for the user and the examiner.
  2. **Free trial (the user creates the account).** Take the 5 BUILD map-market days with the most wallet fills and
     bo3-parsed rounds, as `book_snapshot_full`, or `quotes` plus `trades` if the full snapshot is periodic.
     - Label its levels with the validated fingerprint F_mkt (X92). Check the label against calldata: at least 90% of
       its filled orders should link to an add.
     - Then run, pre-registered and uncensored, the counts of V moves per round against deaths (finding 18), the
       before-anchor share in decided-early rounds (finding 7), and |dV| at feed messages. K predicts a mixture of
       1-3c in-round steps and large end steps; R predicts about one large step per round.
  3. **Public message clock.**
     - Waves: at least 2 distinct non-own makers cancelling, or at least 3 levels pulled, within 30 ms on any book of
       the event.
     - Measure the share of its dark V-changes with a wave in [-50, 0] ms, against a shifted null.
     - Measure the inter-wave refractory after round ends on the bo3-aligned clock, as a check of the clock.
  4. **Anchors on VALIDATE (21-22 Oct; needs the $99 tier).** Within one tick at signing for:
     - floor(J at t - 100 ms) with own levels removed;
     - K minus others' best ask on the complement;
     - the last match-time print.

     Each against the block-time print, 0.322. Then put the best one in `evaluate()` as a reported anchor, never fitted
     on VALIDATE.
  5. **$99 tier.** All 229 maker-regime markets plus their round handicap / totals books: X164 and X47b historical, and
     the E3 screen re-run with book events (waves, queue depletion at the touch) at their server time.
- **Data needed.** A Telonex account (the user's decision: free trial or $99 a month), plus the calldata and bo3 rounds
  already cached.
- **Signature if true.**
  - Label precision ≥ 0.9.
  - At least half of the dark V-changes sit on a public wave at ≥ 3x the null, so the dark messages are visible on the
    public book in real time.
  - J at t - 100 ms is ≥ 0.45 within one tick on VALIDATE, at least 0.10 above the print.
  - The uncensored per-round count rises with deaths (K), or stays at 1-2 with a 7-27-s refractory after ends (R).
- **If false.** The archive has no October CS2 coverage, or its snapshots are 1 s or coarser. Then close with the
  availability response, and the live lab remains the only book source.

### P3. Vendor fingerprint from pre-game messages, at the vendor level (strong form of X206's key-free part)

- **Hypothesis.** LLF lists "map and map picks" for CS2, and the draft for Dota and LoL, among its data points. If it
  is the feed, subscribers receive veto messages before map 1 and take on the Map-2 / Map-3 and match books at the
  in-play fan-out lags. Those takes should come in one burst per Bo3 event, near the veto's end. A reader of server logs,
  CSTV or an in-server observer cannot see an off-server veto, only the map load.
- **Why it fits.**
  - X206's veto test ran only on the wallet's own V-changes: 70 pre-game, with no event re-priced on two map books.
    That is untestable, and the wallet's pre-game bids sit 1-2c under the print anyway (X144). The vendor-level sample
    is wallet-independent and larger.
  - In 16-22 Oct, 104 of 8,342 wallet-free group-P takes are signed before the scheduled start: 57 on map books, 47 on
    match books. Their timing before the start is 10 in (-60, -30] min, 20 in (-30, -15], 13 in (-15, -5] and 61 in
    the last 5 min. Group G adds more.
- **Test.**
  1. Pre-game fan-out clusters: at least 2 distinct subscribers within 300 ms, wallet-free txs, with the in-play lag
     order (P4e first, IQR ≤ 40 ms).
     - Rate per minute by time to start against a ±30-60 s shifted null.
     - Concentration per event: share in the busiest 3-min window.
  2. For Bo3 events, the cluster's direction on each Map-N book against the team that picked map N. Take this from bo3
     `matches/<slug>?with=games` (map order); verify whether a pick field exists before relying on it.
  3. For Dota, on development blocks: subscriber and operator Dota takes during the draft, against the picks in
     `tommy_dota_rt` GetRealtimeStats snapshots. Check first that the snapshots carry draft picks.
  4. Fetch pre-game public taker calldata for more events if the 16-22 Oct cache is thin there. Report the minimal
     detectable rate.
- **Data needed.** `calldata_pub` (have), plus more pre-game public txs of the 384 events (development; fetchable), bo3
  match objects (cached / key-free), and `tommy_dota_rt` (development blocks, via `iter_live`).
- **Signature if true (LLF-like).** Pre-start clusters at the in-play lag structure, at least half of them inside one
  1-3-min window per event 5-30 min before the start, buying on Map-N books the team that picked map N in at least 60%
  of cases.
- **Signature if false (log or relay reader).** No pre-start clusters beyond the map-1 start (warm-up / knife), and none
  on Map-2 / Map-3 books before map 1 ends.

### P4. A wallet-independent record of what it sees, for the forward exam (data integrity; new)

- **Hypothesis.**
  - `clob_wallets` books exist only after a studied wallet trades the market, so any book-derived input from it is
    conditioned on the wallet's own presence.
  - After 11-03 00:00 the own wallet-independent recorders stop, so the examiner's future blocks would have neither
    wallet-independent books nor Valve Dota state. Both are inputs a frozen rule may need (P2's anchors; the Dota half,
    about 55% of fills on 10-31 12-18).
- **Why it fits.** The brief's description of `clob_wallets`; the hard stops in `state.json` `live_lab`; critique 5.
- **Test.**
  1. On the development blocks 10-31 00-06, 10-31 12-18 and 11-01 06-12, per market:
     - the first `clob_wallets` record against the first trade of any studied wallet;
     - `clob_wallets` coverage of events the wallet did not trade, against `tommy_cs2_near`;
     - the AUC of "the market has `clob_wallets` records in the bin" for the wallet's presence.
  2. If it leaks, forbid `clob_wallets` as a rule input in `evaluate()`, and say so in FINAL_RULE.md.
  3. Start replacements before the 11-03 stop: a wallet-independent recorder of every esports book in play (CS2 / Dota
     / LoL, near-touch format, unit filing) and a `tommy_dota_rt` successor. Give them new hard stops after the last
     planned exam block, keep them within the live-lab limits, and record them in `live_lab`.
- **Data needed.** Live recordings via `iter_live` (development blocks only) and the studied wallets' development-block
  trades.
- **Signature if leaky.** In more than 90% of markets `clob_wallets` has no record before the first studied-wallet
  trade, and it has none for untraded events. Its "presence AUC" is then near 1 by construction.

## Ranked user asks (one list, by decisiveness for the exam)

1. **PandaScore token with live LLF access**, recorded live (P1). This is the only route by which the price item can be
   examined. The free tier alone settles the coverage flag.
2. **A Telonex account** (free trial, then possibly $99 a month), development dates only (P2). It gives the uncensored
   V, the public message clock and the book anchors, and the examiner may be able to use it on h1 / h2.
3. **Demos (X37 / X122 / X193).** Decisive for R vs K (V's function), but not an examinable input (critique 2).
4. **HLTV HAR (X64).** Kick VOD (X4 / X22) only after the above.
5. **The exam wallet list** (attributed accounts). This is unchanged from iteration 15.

## Not worth budget (measured)

- **Builder and metadata codes.** All 36,666 of the wallet's orders and every group-P member's orders in its txs carry
  `builder = 0`. Nonzero builders are on about 3.6k of 128.8k orders, retail apps spread over many makers. No vendor or
  platform fingerprint.
- **eventMetadata `context_requires_regen`.** 0 of 63 non-GRID events without it were traded, but those are one-market
  tier-4 / tier-5 events: median 1 market and about $13 of pre-event volume, against 3 markets and about $1.3k with the
  flag. The flag tracks event size and activity and is probably set after listing. Keep it out of every rule.
- **bo3 per-kill data.** `/games/{id}/kills`, `/round_kills`, `/game_kills`, `/replay` and `/heatmaps` return 404, and
  `round_map_data` is null on the 10-16 game. bo3 holds per-team round stats (alive_time, first kills, plants,
  equipment) but no kill times.
- **PMXT** after 2026-08-09 (critique 1).
- **The fee-threshold reading of the dark share** (critique 3).

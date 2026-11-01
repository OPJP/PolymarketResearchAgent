# Panel, iteration 12: mechanics and on-chain forensics (fresh eyes)

Lens: how the orders are built and by which process. Covers which accounts that process signs for, what the 504-ms loop
reacts to, and how the event path picks its price.

Written 2026-11-01, about 08:50-09:40 UTC, inside the development block 11-01 06-12.

## What I read and what I ran

I read:

- BRIEF.md;
- NOTES.md: iteration 12 in full, iterations 1, 6, 7 and 11 by section;
- state.json: the catalog A1-X171, the components, the target metrics;
- FINAL_RULE.md, by section;
- panels/iter11_mechanics.md in full, plus the sibling checks in iter10_mechanics.md and iter11_assumptions.md.

`tools/sealed.py tommy-cs2-maker` reports no released lots and the future examined up to 10-31 00:00. The current block
(11-01 06-12) is development.

Every record I used is development data:

- 16-22 Oct: `calldata_all`, `orders_inv`;
- the 10-31 12-18 block (BUILD-live): `own_bursts_dev`, `level_events_dev`, `others_mid_dev`, `calldata_dev`,
  `dev_markets`, and the iteration-12 tables `slot_vrel_rows`, `own_occupancy_rows`, `withdrawal_episodes`.

I also made about 40 chain-state calls on publicnode, read-only: `eth_getCode` and `eth_getTransactionCount` at `latest`
for 17 EOAs and wallets. These are current state, not tied to any market unit. I made no logs or activity calls.

I did not read the 11-01 recordings and opened nothing in `.cache/live/sealed/`. I wrote nothing outside this file. My
scripts are in
`C:\Users\REMOTE~1\AppData\Local\Temp\claude\C--Dev-trading-research-PolymarketResearchAgent\97f207f2-bd1a-4cdb-a63d-2290c58d22c3\scratchpad\m12\`.
Each process ran for under 3 minutes and under 300 MB.

## Critique: what the investigation is missing or getting wrong

### 1. The C1 closure missed a second account signed by the same process

C1, X14, X95 and X110 closed siblings at the key level ("no shared key"). Iteration 7 read the two merge-law siblings
as "a shared maker design (different configs and processes)". The iteration-11 assumptions panel tested only
0xf1f2b3c6 ("only 29 synchronous orders"). Nobody ran the same-process test on the other sibling, 0x52661b8e.

**Its orders** (`calldata_all`, 16-22 Oct):

- 1,064 orders, every one a 5-share maker BUY, on 38 tokens, all of them tokens the wallet trades.
- They run only from 10-21 15:05 to 10-22 12:26 UTC, inside the wallet's daily session (15-23 h, then 08-12 h after
  the overnight restart).
- 991 of the 1,064 sit at a price where the wallet also has a filled order on the same token.

**Signing lag behind the wallet's nearest same-token, same-price order.** The table compares it with the wallet's known
book followers and two feed co-subscribers.

| Maker | Orders | [-5, 0) ms | [0, 5) ms | [5, 10) ms | [20, 50) ms | [50, 100) ms | On the wallet's 504-ms tick (±15 ms; uniform 6%) |
| --- | --- | --- | --- | --- | --- | --- | --- |
| **0x52661b8e** | 1,064 | 19 | **78** | 9 | 43 | 26 | **21.1%** |
| 0x51dbdd2b (co-subscriber) | 2,209 | 5 | 25 | 30 | 47 | 56 | 9.2% |
| 0xe8e1b119 (follower) | 8,181 | 3 | 4 | 5 | 45 | 222 | 5.6% |
| 0xaeb90af4 (follower) | 2,937 | 3 | 4 | 2 | 52 | 208 | 5.2% |
| 0x68915897 | 2,207 | 12 | 2 | 1 | 83 | 19 | 5.1% |
| 0xf1f2b3c6 (merge-law) | 899 | 0 | 1 | 0 | 2 | 3 | 6.1% |

How to read the lag profiles:

- A book follower cannot sign before the wallet's order reaches the book. The wallet's post latency is about 24 ms. The
  followers peak at +20-200 ms, as they should.
- 0x52661b8e peaks at 0-5 ms after the wallet's signing. At that point the wallet's order is not yet on the book.
- Its signed orders per millisecond are 617 singles, 121 doubles and 49 triples: ladders.
- Of the 133 sibling orders signed 0-10 ms after a filled wallet order on the same token, 64 match a price in that
  wallet burst's filled set. The other 69 sit 1-4c below it (the burst's unfilled slots).

**Phase.** The 21.1% includes the co-signed orders. Its 758 non-co-signed orders fall 0-72 ms after the wallet's tick at
about twice the uniform rate (207 against about 108 expected).

**Owner keys.** Of the 14 sampled owner keys of sigType-3 makers in its markets, exactly two are EIP-7702 accounts
delegated to 0x63c0c19a282a1b52b07dd5a65b58948a07dae32b:

- the wallet's owner (nonce 3);
- 0x52661b8e's owner 0xe6f64514 (nonce 2).

I believe this is MetaMask's EIP7702StatelessDeleGator; verify it from the verified source. The other 12 are plain EOAs.

The wallet owner's only outgoing transfer in 10-12..H ($2,000, `funding_graph.json`) went to 0x116342d6. That address
is a third EOA delegated to the same contract (nonce 9). The two 0x1163...3829 look-alikes with $0 transfers are address
poisoning.

Two smaller points:

- The sibling's deposit wallet is a beacon proxy (146 bytes, ERC-1967 beacon slot), against the wallet's ERC-1967
  proxy with immutable arguments (125 bytes). It was created later, from a newer factory.
- The owner of $2,000 inflow, 0xf70da978 (nonce 3.3M), is an exchange hot wallet.

**Reading.** One bot process, run by one operator, signs a second, 5-share account. It uses the same price, the same
ladder and the same loop, and signs 0-5 ms after the wallet. The C1 / C4 closures and the "different processes"
sentence should be corrected. The operator's other accounts are a data source nobody has opened (proposal P1).

### 2. The loop attribution (X158) used unsigned changes, so it is the weak form of the public-follower test

Finding 6 counts "any same-book non-own change in the previous tick" (67% against 53% at control ticks). Finding 14
tests the pull toward the mid LEVEL, on adds only. Neither asks whether the quiet step follows the SIGN of the recent
public move.

The rebuilt own-top path on token 0 includes pulls (`own_occupancy_rows`, 726 changes). I kept the 134 "quiet" ones:
no triggered own burst in [-600, +30] ms and no trade within ±300 ms. For these, the share whose sign agrees with the
change of the others' mid in a window, among changes where the mid moved in that window:

| Window before the step (ms) | [-10000, -5000] | [-5000, -2000] | [-2000, -1000] | [-1000, -500] | [-500, -30] | [0, +1000] |
| --- | --- | --- | --- | --- | --- | --- |
| Quiet steps | 0.58 (60) | 0.51 (59) | 0.64 (28) | **0.875 (40)** | **0.87 (23)** | 0.74 (54) |
| Not-quiet steps | 0.42 | 0.56 | 0.63 | 0.64 | 0.56 | 0.76 |

So when the public mid moved in the last second, the quiet step goes the same way 87% of the time.

The forward direction is weak, though. After a public mid move under the same filters (760), the wallet steps within
1.5 s in 12.8% of cases (control 7.8%); it steps the same way in 9.3% (control 3.7%). At most about a third of the
quiet steps are a lagged public follower.

The level is not a filtered mid either. The new top against round(EMA_tau(mid) - 2c), offset fitted on the first half
and scored within one tick on the second half: tau 0 gives 0.415, 1 s gives 0.368, 4 s gives 0.315. Persistence of its
own top gives 0.723.

This tightens the wall account: "at most about 14 points" becomes about a third of quiet steps in sign, none in level.
It also marks where a signed ledger can still gain (proposal P2).

### 3. The "no drift" verdict on the loop (finding 12, branch c) rests on adds only

Adds can only show up-moves on a full ladder, so the sign statistics are biased. With pulls included and fills
excluded, consecutive quiet steps on a book are 0.605 same-sign against 0.526 under shuffles (p 0.19, 38 pairs). Runs
of three or more occur at 0.03 per change against 0.015.

So branch (c) is not rejected: the test is underpowered. It should be re-run on pooled VALIDATE-live with pulls (P2,
step 5) before the wall account calls the quiet value drift-free.

### 4. The frozen price anchor is weaker than the best admissible one

v5 freezes the last print (0.322). The brief excludes own state only from the presence item. For price, the target is
"within one tick ... against the best trivial anchor", with own state reported separately. X137 measured own
persistence at 0.500 (VALIDATE, historical).

The best honest examinable price is therefore about 0.50, tagged own-state, provided the previous order was visible
point-in-time. Its fill block must lie before the new order's signing, and the 0.500 should be re-checked for that
look-ahead.

On h1 / h2 nothing book-based can be scored, because no books exist for those lots. The wall account should state the
historical price bound as persistence, not the print.

### 5. Negative checks (so nobody redoes them)

**A. The loop does not react to its own fills (inventory).**

- Own maker fills in the previous tick, at match = taker sign + 1,040 ms (557 fills):
  - on-tick untriggered adds 0 of 163 (shifted control 1.0%);
  - untriggered pulls 0 of 63 on tick and 1 of 119 off tick;
  - triggered adds 2.5% (control 0.8%).
- The untriggered label already excludes trades in [-300, 0] ms, but the 300-520 ms part is empty too.

**B. No cost-basis pair cap.**

- Historical maker orders (16-22 Oct, `orders_inv`). The sum of the price on token X and its latest own fill price on Y
  (published before signing) has p10 / p50 / p90 = 0.87 / 0.98 / 1.07 when it holds unpaired Y.
- The best constant K is within one tick of that sum in 0.21 of cases (0.30 for fills younger than 10 s, 0.16 after its
  takes).
- With a 10-fill VWAP cost it is 0.11-0.13. V is not K minus the cost of held inventory.

**C. Re-entry after event-wide withdrawals joins the public book more than other fresh ladders do.**

| Population | n | Others' best J exact | J within one tick | J + 1c within one tick | Its own top before the withdrawal, within one tick |
| --- | --- | --- | --- | --- | --- |
| First add burst within 1.5 s after an episode ends (64 episodes) | 77 | 0.455 | 0.727 | 0.61 | 0.53 (19) |
| All fresh bursts | 448 | | 0.551 | 0.455 | |

**D. Per-book quiet intervals sit on multiples of 504 ms, with no per-book period.**

- The intervals between bursts on one book side sit on multiples of 504 ms (65 / 55 / 32 at 1 / 2 / 3 ticks against
  12 / 8 / 7 half a tick off).
- There is no peak at a book-specific period, so it is not round-robin servicing.
- Same-tick co-re-pricing is uncommon:
  - on the complement token: 16.6% of untriggered adds and 24.5% of triggered adds (about 2-4% at ±1 tick);
  - on another market of the same event: 1.7-6.2%.
- Each book is re-priced separately on the shared tick.

## Proposals, ranked by the chance they close the gap

### P1. Map every account the wallet's process signs for, and use them as natural experiments on V (new data; strong form of C1 / C4 / X95 / X110 / X166)

- **Hypothesis.** The process that signs the wallet's orders also signs for other accounts:
  - at least 0x52661b8e (5-share configuration, 10-21 / 10-22);
  - possibly accounts owned by 0x116342d6 or other EOAs delegated to 0x63c0c19a.

  Some of these accounts run other configurations, periods or markets: GRID CS2, other titles, earlier dates. There the
  same valuation and ladder can be observed against inputs that are public, or against a different input mix. This
  shows which parts of the quote are configuration (size, depth, band) and which are model (V).
- **Why it fits.**
  - Critique 1: the 0-5-ms same-price co-signing, ladders replicated slot by slot, the shared session, the shared
    EIP-7702 delegate (2 of 14 owners), and the owner's $2,000 transfer to a third account with the same delegate.
  - The operator ran a GRID taker until 10-16 and still runs a 504-ms loop with an event path. A process that signs for
    several accounts may also quote markets the wallet left.
  - The weak form of the salt-PRNG test (X96: 0 consistent systems for strides 1-9 inside the wallet's 5-order bursts)
    assumed that nothing else draws randomness between the wallet's orders. Orders of other accounts in the same
    process break that assumption. This gives one possible reason the weak form failed.
- **Test** (development periods only).
  1. **Delegate scan.** Run `eth_getCode` at `latest` (state only; one call per address on publicnode, since drpc
     refuses batches over 3) on the owner keys of every sigType-3 maker in `sig_signers` and in its markets'
     `calldata_all`. Flag the ones delegated to 0x63c0c19a.
  2. **Funding links.** Pull October USDC / USDC.e `Transfer` logs to and from 0x116342d6, 0xe6f64514 and 0x52661b8e
     (address-filtered `eth_getLogs`, publicnode, blocks 95.37M-96.00M). Then find the deposit wallet or Safe of each
     linked EOA:
     - a factory prediction, as `lineage.py` did;
     - or an `owner()` match among makers.
  3. **Same-process test** for every candidate account against the wallet, where they overlap:
     - the share of its orders signed 0-5 ms after a wallet order on the same token, against [5, 50) ms and against the
       follower controls in the table above;
     - its phase on the wallet's 504-ms grid.
  4. **Histories.** For every confirmed account, fetch data-api activity before H (titles, sessions, sizes, MERGE
     cadence against the 300.22 + 7.28-s law), then decode calldata for its markets outside the wallet's universe.
  5. **Decode V where inputs are public.** If an account quotes GRID CS2 or another title with public in-play state,
     inverse-fit its burst tops there:
     - against the bo3 per-round state;
     - on live blocks, against the sports socket's GRID round scores;
     - with the X171 HMM.

     If it quotes the wallet's events with another configuration, compare V burst by burst (same ms, same token). The
     differences isolate configuration terms.
  6. **Historical uncensoring of the ladder (VALIDATE-only).** On 10-21 / 10-22, the union of both accounts' filled
     orders in co-signed bursts recovers unfilled slots of the wallet's ladder. Score the frozen X163 machine on that
     historical record, oracle V = the co-burst top. This is the first non-live check of the mechanism.
- **Data.** `sig_signers.parquet`, `calldata_all`, `funding_graph.json`, publicnode state and logs (October, address
  filters), data-api activity before H, and Gamma listings for any new markets.
- **Signature if true.**
  - One or more further same-process accounts (0-5-ms co-signing, the 504-ms phase, the merge law).
  - One of them trades outside the wallet's universe before H, giving a second window on the same valuation with
    observable inputs.
  - Or a configuration difference that separates the size / depth rule from V.
  - The historical X163 set unit is ≥ 0.85 with the co-burst oracle.
- **Signature if false.**
  - 0x52661b8e is a one-day 5-share test account and no other instance exists.
  - C1 then closes with "one operator, two accounts, one process", which is a correction of the current closure. Step 6
    still gives the historical validation of the ladder mechanism.

### P2. A signed per-tick ledger of the 504-ms loop, with pulls, queue state and public deltas (strong form of X158 step 4 and of E16 / E17)

- **Hypothesis.** On each tick, the loop decides per book side among hold, ±1c, a jump, or pull-all. It does so from
  (a) a private value and (b) a small set of public, signed book deltas since its last service of that book. The
  candidates for (b):
  - the others' mid or best-quote move in the last second;
  - others joining or leaving at its top;
  - its gap to the others' best.

  Part (b) is examinable on future blocks. The test measures exactly how much of the quiet value it carries.
- **Why it fits.**
  - Critique 2: when the mid moved in the previous second, quiet steps agree with it 87% of the time (63 cases), against
    51-58% for moves 2-10 s earlier.
  - The forward rate is low (9.3% against 3.7%), so the public part has a ceiling, and it is unmeasured.
  - Critique 3: the sign-run test of finding 12 is biased by the adds-only sample.
  - Iteration-11 mechanics check C: others adding at its old top in the previous 1 s precede 45.8% of its up-steps
    against 15.1% of its down-steps. This queue signal was dismissed for lacking +1c specificity, not for lacking
    asymmetry.
- **Test** (fit on BUILD-live, 10-31 12-18 plus the development blocks assigned to BUILD; score on VALIDATE-live
  without refitting).
  1. Rebuild the own-top path for BOTH tokens from validated own levels, adds and pulls included (the occupancy rows
     hold token 0 only). Put it on the 504-ms grid, phase from the latest untriggered burst.
  2. Units: (book side, tick) where it holds a level, with no event-path own action in [-600, +30] ms and no trade
     within ±300 ms. The target is the change of its top in cents.
  3. Point-in-time features. Signed changes, since its last tick on that book and over 0.5 / 1 / 2 / 5 s, of:
     - the others' best bid, best ask, mid and microprice, on the token and on its complement;
     - others' joins and cancels at, above and below its top, and its queue state (alone, ahead, behind; in live data,
       its queue position is the book level's size order).

     Also:
     - its top age;
     - its gap to J;
     - the 1.5-s cooldown;
     - own fills since its last tick;
     - unpaired inventory, with and without (own state);
     - whether its complement or a sibling market moved its own level in the previous tick.
  4. Models: multinomial logistic plus a distilled rule, for example "step 1c toward the sign of the last-second mid
     move when |dmid| >= 1c, else hold". Compare against persistence. Score:
     - exact V on quiet steps;
     - hold accuracy;
     - per order through the frozen X163 machine.
  5. Report sign persistence and run lengths with pulls, by time since the last event-path jump on the event, to give
     branch (c) a fair test.
- **Data.** `tommy_cs2_near` / `clob_wallets` raw books, `calldata_dev{SUF}`, `linked_adds_dev{SUF}` and
  `own_bursts_dev{SUF}`, through the existing runbook variables. The rounds-book clock (X164) is optional, for step 5.
- **Signature if true.**
  - Exact V of at least 0.8 on quiet steps, given its previous top and the public deltas.
  - The quiet class (about 70% of filled orders historically) then becomes scoreable on future blocks through the
    machine. The private part of the price item shrinks to the event path.
- **Signature if false.**
  - Public deltas explain no more than about a third of quiet steps (the forward rate stays near 9% against 4%).
  - The quiet class is then a private input moving with the same information as the market, and the wall account gets
    a measured share instead of "at most ~14 points".
  - With pulls included, runs show (or exclude) the in-round drift.

### P3. The event path's response function: what each triggered action copies, and at what price (strong form of X63 / X80 / X159 step 4)

- **Hypothesis.** The event path is partly a public-book reactive machine. Its triggered pulls and adds (median 17 ms
  after a book change) answer specific precursors:
  - a fast feed-subscriber's cancel wave → event-wide pull;
  - a new best bid posted by another maker after a withdrawal → re-entry at that bid or 1c above;
  - its own take → complement at K - limit.

  The response price is then a deterministic function of the precursor's price for the classes that follow such
  precursors. For those classes it is examinable on future blocks, and these classes include fresh ladders (42% of
  adds).
- **Why it fits.**
  - Off-tick bursts follow a same-book non-own change within 40 ms in 61% of cases (control 19.5%). Withdrawals start
    with triggered pulls (33 of 64) and end with triggered adds (53 of 64).
  - Check C: re-entry bursts after event-wide withdrawals are at others' best exactly in 0.455 of cases and within one
    tick in 0.727, more than fresh ladders generally (0.551). A precursor-specific rule should beat both.
  - X80 found its pulls at pack-only events come 0-30 ms AFTER the first non-own cancel. The precursor's identity was
    never used as a feature for the response price.
- **Test** (BUILD-live fit; score on VALIDATE-live).
  1. For every triggered own burst (adds and pulls, about 2,550 on BUILD-live) and every withdrawal start and end,
     list the public changes in the preceding 40 ms with:
     - type and book (same token, complement, sibling market);
     - price relative to its top and to J, and size;
     - the maker, by size fingerprint and the calldata-linked add label;
     - whether that maker is in group P, the pack, or the six fast makers.
  2. Build a precursor-class by response table: response price minus the precursor's price, and pull scope (one book,
     the market, the event).
  3. Freeze a rule per class on BUILD-live. Score exact V and within one tick on VALIDATE-live, by class and pooled with
     the X163 machine.
  4. Control: the same precursor classes at times when it held no level, or was in cooldown, show whether the response
     is conditional on its state.
- **Data.** The raw books, `linked_adds_dev{SUF}`, `calldata_dev{SUF}`, the group-P and pack membership lists, and
  `withdrawal_episodes`.
- **Signature if true.** A few precursor classes cover at least 60% of triggered adds, with exact V of at least 0.8 in
  each. The re-entry price becomes "the precursor's price plus a class constant", and part of V turns public at the
  millisecond.
- **Signature if false.** Responses are not set by the precursor (exact < 0.5 in every class). The triggered actions
  are co-receptions of the same private messages that the other makers also act on, and the wall account can quantify
  that co-reception share.

### P4. The salt stream under multi-account signing (strong form of X96; lower priority)

- **Hypothesis.** The process draws salts from one generator for all the accounts it signs. Those are
  `round(Math.random() * Date.now())` in the TypeScript client, and the sibling also has ms-scale salts. The weak-form
  search failed because orders of other accounts sit between the wallet's orders in the stream.
- **Why it fits.** Critique 1: the sibling's orders are signed 0-5 ms after the wallet's in the same burst. A
  co-signed burst therefore supplies consecutive outputs in a known order: the wallet first.
- **Test.** On the 10-21 / 10-22 co-signed bursts, run the existing V8 xorshift128+ z3 setup on the merged sequence
  (wallet orders, then sibling orders). Use both cache orders and strides up to 64. If a state is recovered, step it
  forward through every later salt of either account. Each unexplained draw between two known orders counts orders
  signed for unseen accounts, or unfilled orders.
- **Data.** `calldata_all` (salts, sign_ms) of both accounts.
- **Signature if true.** A recovered state. It gives a historical count of the process's unfilled orders, a presence
  label for h1 / h2 that needs no book, and a census of the hidden accounts' orders.
- **Signature if false.** No consistent system on merged sequences either. The salts are then not drawn from a
  recoverable V8 stream (another engine or a cryptographic source), and X96 closes.

## Overlap with the ledger, the catalog and the other panels

- **P1.**
  - Existing: C1 / X14 / X52 (owners differ), X95 (merge-law siblings, read as different processes), X110 (no shared
    key), X166 (no predecessor under the owner key), X74 (funding graph of the wallet only).
  - New: the same-process test (0-5-ms same-price co-signing, the phase), the EIP-7702 delegate link, the third
    account, and the use of these accounts as natural experiments and for historical uncensoring of the ladder.
- **P2.**
  - Existing: X158 steps 1-3 (unsigned attribution; adds-only sign runs), finding 14 (level pull, adds only), X63 / X94
    (the join rule and others'-mid pulls on BUILD-live).
  - New: signed deltas with a located 0.5-1-s lag, pulls included, queue state, and an exact-V score through the
    machine.
- **P3.**
  - Existing: X63 (join rule within 100 ms), X78 / X80 (pull timing against the first non-own cancel), X121 / X136
    (co-receiver cancels), X159 (withdrawal episodes).
  - New: precursor identity and price as the input of the response price, and the re-entry rule.
- **P4.** Existing: X96 (weak form, wallet-only bursts). New: the merged multi-account stream.
- **Not proposed, because covered elsewhere.** The Thunderpick suspension coincidence (X144 / X159 step 3 / X168), the
  rounds-book clock (X164), demos (X122 / X37), and Valve's live Dota state (X118 / X167 step 2).

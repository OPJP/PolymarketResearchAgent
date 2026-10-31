# tommy-cs2-maker: frozen rule v1 (`tommy-v1-league-ladder`, iteration 1, 2026-10-31)

Wallet TommyLeePeeca `0x0063b23cdeb43166d6c0246c05baaf9b9bd72dd2`. Development data: 16-22 Oct 2026 (maker regime).
BUILD = gameStartTime in [10-16, 10-21), VALIDATE = [10-21, 10-23). Code: `code/final_rule.py` (`evaluate(start_ts,
end_ts, intervals=None)`), constants in `code/final_rule_constants.json` (fitted on BUILD). Nothing here is
exam-verified yet. The rule does not meet the high-accuracy target. The informed part of the strategy (the taker
trigger) is described but not decoded.

## The rule, component by component

| Component | Rule | Tag | VALIDATE evidence |
| --- | --- | --- | --- |
| Selection | CS2 match-winner and map-winner markets. League score `s_meta = (league markets traded + 5 * tier rate) / (league markets + 5)` from BUILD. Trade every market of an event when `s_meta >= 0.344`. In-play only. | VALIDATE-only | AUC 0.877, recall 0.636 at lift 2.65 (358 markets, 107 traded). Pre-game activity baseline 0.882. Inside a traded event it trades 97% of markets. On 10-31 it skipped all 5 development-unit events, all from leagues it never trades. |
| Timing (maker) | Quotes from game start until the map or match ends, re-signing all the time. | VALIDATE-only (presence), hypothesis (cause) | Presence AUC 0.827 vs activity baseline 0.899. Filled orders are 15.8 s old at the median. Signing rate is 3.0x baseline 0.5-1.0 s after any public taker signs, the same as other makers. |
| Timing (taker) | Not decoded. Fires about 30 s before the next round-end price jump. | hypothesis | Next jump of 4c or more comes after a median 32-37 s (90-94 s at random times). |
| Side (maker) | Buys both outcome tokens: no side choice at market level. | VALIDATE-only | 97.4% of bought shares end in complete pairs. 67% of its maker fills are on the side it is short of. |
| Side (taker) | Buys the team that wins the round in progress. Input unknown. | hypothesis (input), VALIDATE-only (effect) | Next jump in favour 64.2% vs 51.1% at random times. Event-level bootstrap gain +0.130 [0.095, 0.166], p < 0.00025 (BUILD +0.156). |
| Price (maker) | BUY orders on whole cents, ladders 1c apart. Best bids of a two-sided burst sum to about 0.97. Anchor: last public print rounded to the cent. | VALIDATE-only | 100% of maker prices on whole cents. Anchor exact 11.5%, within 1c 30.5%. Placement against the touch is not decoded (needs books). |
| Price (taker) | Limit 0-2c above the best available ask. | VALIDATE-only | Limit minus best fill: median 1c (p90 4c). Usually fills one level. |
| Size | Maker: 100 shares (10 or 11-99 when inventory is small). Taker: 1000 or 2000 shares (23%), otherwise odd sizes (median 542 shares, $235). | VALIDATE-only | Maker 100-share accuracy 88.3%. Taker orders median 12% filled. |
| Exit | Never sells. Merges complete pairs and holds the residual to resolution. | VALIDATE-only | Weighted pair cost 0.9785. The residual ends on the losing side 68% of the time. |

## Target metrics on VALIDATE (`state.json` `target_metrics`)

- `presence_auc` 0.827 vs `presence_baseline` 0.899: no gain. The LightGBM fill-presence model reaches 0.952, but the activity-only version already gets 0.942, so that is co-occurrence.
- `selection_auc` 0.877, recall 0.636, lift 2.65, vs `selection_baseline` 0.882: no gain. League score plus activity reaches 0.920.
- `side_accuracy` and `side_baseline`: not applicable for the maker component, which is two-sided. Taker side: next jump in favour 0.642 vs 0.511.
- `price_within_tick` 0.115 (last-print anchor; 0.305 within 1c).
- `pnl_corr_pearson` and `pnl_corr_spearman`: none. There is no executable rule yet.
- `coverage_fills` 0.927 and `coverage_abs_pnl` 0.990: the Dota 2 markets fall outside the universe.

## Why it works (economic mechanism, VALIDATE-only)

Settlement PnL on 16-22 Oct was $13.1k, before $2.05k of maker rebates and $2.2k of taker rebates, and after none of its taker fees. It has two sources:

1. **Informed taker orders**, about 70% of the PnL. They are 15% of its USD volume and earn +6% (BUILD +6.7%, VALIDATE +5.2%).
   - The markouts grow slowly: -0.14c at 5 s, +1.06c at 30 s, +2.33c at 300 s.
   - It buys the team that goes on to win the round in progress, about 30 s before the market reprices at round end.
   - The losers are the makers whose quotes are stale during the round, and the takers who sell after a drop.
   - It is paid for information about in-round game state that the public tape does not carry.
   - A public "buy after the drop" taker loses 4.5-9.2% on the same markets and matches only 3.5% of its taker orders.
   - Caveat: by an event-level bootstrap, the settlement edge alone is not significant in either split (p = 0.16 and 0.21). The round-level next-jump result is (p < 0.00025).
   - A few other informed takers buy the same team in the same or next block. They share the trigger; they are not copying it. Two of them are also its top counterparties on the maker side.
2. **Two-sided ladder making with pair merging**. Its maker fills earn about +0.5% at settlement. Locked pairs are worth +$21.6k, but the unpaired residual loses about $8.4k to adverse selection. Rebates add about 30% on top.
   - This part is ordinary: about 30 other makers in the same markets show the same quote lead and timing, and several earn more per fill.
   - It is paid for supplying liquidity to in-play takers, helped by the 1-s in-play taker delay.

## Can a normal user deploy it now

- **Maker component.** Deployable in principle. It needs:
  - a CLOB client that re-signs 100-share whole-cent ladders on both tokens within about 1 s of book activity;
  - automatic merging of pairs;
  - about $10k of capital (peak capital at risk was $9.6k).
  On its own it earned only about +0.5% on fills plus rebates in 16-22 Oct. A replicator would also join the queue behind the incumbents, so the expected edge is close to zero or negative.
- **Taker component.** Not deployable from public data. It depends on an in-round game-state source that is faster or richer than the public tape. Candidates are a scorebot or data feed (GRID, HLTV scorebot, bo3.gg live) or a low-delay stream. That source has not been identified, and the edge exists only in the leagues it selects.
- **Current conditions.** Market parameters did not change between 10-01 and 10-22: fee `sports_fees_v3` rate 0.05, rebate share 0.15, 1-s delay, rewards 50 / 4.5c. Whether the strategy still runs after 10-23 is sealed for this agent.

## Not explained yet

- The taker trigger's input, and its timing within the round.
- Maker quote placement against the touch, and the cancel and requote rule.
- Why this set of leagues.

See NOTES.md, "Next iteration".

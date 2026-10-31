# mo-money (`0x32ed2e546b187ca15e2841edc82b22c713cf8ec3`)

Leaderboard rank 242 (monthly PnL). Verdict: **REJECT**. Archetype: Directional maker on crypto Up/Down windows (three-wallet cluster: bosona, almach, mo-money).

Profile: https://polymarket.com/profile/0x32ed2e546b187ca15e2841edc82b22c713cf8ec3

## Mechanism

89% of sampled fills are maker fills on-chain. BTC 5m is 57% and BTC 15m 27% of its volume, the rest hourly, 4h and ETH/SOL windows. Its profit is the directional residual ($96,917, residual win rate 58%); the locked pair spread is -$24,845. Shared transactions in 30 days: 6,876 with bosona, 6,750 with almach; about 80% of its markets are shared with the other two.

## Criteria

| Criterion | Status | Evidence |
| --- | --- | --- |
| Profit significant, not luck | pass | pre-selection 237d: HAC t=5.7, Holm p=6.6e-05, bootstrap p=5.0e-04; deflated Sharpe 1.000 |
| Net profit above $50k/month | pass | last 30d $84,639; median month $97,178 |
| Constant returns (low std) | pass | annualized Sharpe 12.5; positive weeks 95%; positive months 100% |
| High % profit | pass | 1621%/month: 30-day PnL $84,639 on peak capital at risk $5,222; counting the on-chain collateral too ($40,546), at least 185%/month |
| Trades verified on-chain | pass | 200/200 sampled fills confirmed in Polygon OrderFilled events; 89% maker fills (95% CI 84%-93%), 77% of USDC |
| Reverse-engineered rule matches the wallet | partial | BTC 5m directional maker: stratified AUC 0.497 vs rotation null 0.504 (max 0.603), p=0.52; rule flags 36% of the wallet's decisions at 1.1x the base rate; BTC 5m spot-reactive maker: stratified AUC 0.564 vs rotation null 0.501 (max 0.574), p=0.045; rule flags 22% of the wallet's decisions at 3.4x the base rate; BTC 15m directional maker: stratified AUC 0.506 vs rotation null 0.490 (max 0.584), p=0.34; rule flags 33% of the wallet's decisions at 0.9x the base rate; BTC 15m spot-reactive maker: stratified AUC 0.471 vs rotation null 0.522 (max 0.617), p=0.91; rule flags 10% of the wallet's decisions at 2.4x the base rate; BTC 5m latency taker: stratified AUC 0.523 vs rotation null 0.540 (max 0.741), p=0.58; rule flags 0% of the wallet's decisions at 0.0x the base rate; BTC 5m spot-reactive maker on Binance spot: stratified AUC 0.597 vs rotation null 0.496 (max 0.596), p=0.005; rule flags 3% of the wallet's decisions at 3.1x the base rate; the same, frozen, on 2,000+ unseen windows: stratified AUC 0.522 vs rotation null 0.504 (max 0.516), p=0.0099; rule flags 5% of the wallet's decisions at 2.0x the base rate |
| Rule profitable in held-out PIT backtest | fail | public-data directional maker, BTC 5m strict -13.5% (5,973 fills, p(profit)=1.00); first-in-queue bound -12.8% (6,488 fills, p(profit)=1.00); BTC 15m strict -18.8% (3,057 fills, p(profit)=0.99); spot-reactive maker at 2 s, 5m strict -6.0% (266 fills, p(profit)=0.88); at-touch -4.1% (370 fills, p(profit)=0.88); 15m strict at 3 s +1.1% (179 fills, p(profit)=0.43); fixed-price resting bids (0.05-0.40, either side, no data) -81% to -45% on the same TEST windows; reviewer market-anchored, spot-gated and tape-dip makers: none significant, most lose; its own maker fills in the same windows +3.2% on 5m (p=0.26), +4.7% on 15m (p=0.37) |
| Replicable on a normal computer and connection | fail | every public-data maker version is adversely selected at the latencies a normal connection allows (>= 2 s), even with first-in-queue fills; the wallet's edge points to faster prices than public 1-second data and queue priority. Rebates are not the issue: observed taker-rebate tier Gold (18% of fees); 30-day PnL at the 0% tier $81,999, Gold $84,622, Diamond $88,411, Obsidian $89,285 |
| Conditions still hold now | fail | significant decline inside the last 30 days, last 15 vs prior 15 (p=0.046). [last 30 days p=0.002; decline vs earlier p=0.83; last 15 vs prior 15 p=0.046; trend p=1.00] Its 30-day blocks fell from $154k to $146k, $110k and $85k; A1 had rejected it only because of dormant weeks before it started trading (fixed). |

## Key numbers

- 30-day PnL: $84,639
- PnL at 0% rebate tier: $81,999
- Maker fill share: 89%
- Public-data maker, held out (5m / 15m): -13.5% / -18.8%
- Its own maker fills, held out (5m / 15m): +3.2% / +4.7%

## Why this verdict

- No public-data rule reproduces which passive fills it gets beyond a small association.
- Every public-data maker version loses or is insignificant in the same held-out windows, including first-in-queue bounds.
- Appears to be one operator across three wallets.

## Corrections after the adversarial review (2026-10-31)

- Its own held-out maker-fill returns changed after the tape-pagination fix (the earlier figures missed fills in dense seconds).
- The match test now uses the rotation null; results that were 'at chance' under the old null are reported with the corrected statistic.
- First evaluated in this round: it failed A1 before only because dormant weeks counted as losing weeks.

## Evidence files

- `research/wallets/0x32ed2e546b187ca15e2841edc82b22c713cf8ec3/profile.json`
- `research/wallets/0x32ed2e546b187ca15e2841edc82b22c713cf8ec3/updown_study_btc_5m.json`
- `research/wallets/0x32ed2e546b187ca15e2841edc82b22c713cf8ec3/updown_maker_study_btc_5m.json`
- `research/wallets/0x32ed2e546b187ca15e2841edc82b22c713cf8ec3/updown_maker_study_btc_15m.json`
- `research/stage_a/updown_btc5m_maker_baselines.json`
- `research/stage_a/rebate_dependence.json`
- `research/stage_a/persistence_a1_survivors.json`
- `research/stage_a/collateral.json`
- `research/review_2026-10-31/challenge-crypto-maker-cluster/SUMMARY_all_results.json`

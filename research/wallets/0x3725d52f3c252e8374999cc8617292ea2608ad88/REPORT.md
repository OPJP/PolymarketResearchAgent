# almach (`0x3725d52f3c252e8374999cc8617292ea2608ad88`)

Leaderboard rank 273 (monthly PnL). Verdict: **REJECT**. Archetype: Directional maker on crypto Up/Down windows (three-wallet cluster: bosona, almach, mo-money).

Profile: https://polymarket.com/profile/0x3725d52f3c252e8374999cc8617292ea2608ad88

## Mechanism

92% of sampled fills are maker fills on-chain. BTC 5m is 53% and BTC 15m 30% of its volume, the rest hourly, 4h and ETH/SOL windows. Its profit is the directional residual ($83,545, residual win rate 58%); the locked pair spread is -$22,952. Shared transactions in 30 days: 6,524 with bosona, 6,750 with mo-money; about 80% of its markets are shared with the other two.

## Criteria

| Criterion | Status | Evidence |
| --- | --- | --- |
| Profit significant, not luck | pass | pre-selection 130d: HAC t=8.3, Holm p=5.0e-08, bootstrap p=2.5e-04; deflated Sharpe 1.000 |
| Net profit above $50k/month | pass | last 30d $72,204; median month $99,225 |
| Constant returns (low std) | pass | annualized Sharpe 16.8; positive weeks 86%; positive months 100% |
| High % profit | pass | 1342%/month: 30-day PnL $72,204 on peak capital at risk $5,380; counting the on-chain collateral too ($40,085), at least 159%/month |
| Trades verified on-chain | pass | 200/200 sampled fills confirmed in Polygon OrderFilled events; 92% maker fills (95% CI 87%-95%), 88% of USDC |
| Reverse-engineered rule matches the wallet | partial | BTC 5m directional maker: stratified AUC 0.588 vs rotation null 0.503 (max 0.608), p=0.02; rule flags 43% of the wallet's decisions at 1.2x the base rate; BTC 5m spot-reactive maker: stratified AUC 0.545 vs rotation null 0.501 (max 0.559), p=0.03; rule flags 20% of the wallet's decisions at 1.7x the base rate; BTC 15m directional maker: stratified AUC 0.539 vs rotation null 0.489 (max 0.611), p=0.15; rule flags 32% of the wallet's decisions at 0.7x the base rate; BTC 15m spot-reactive maker: stratified AUC 0.586 vs rotation null 0.513 (max 0.640), p=0.13; rule flags 0% of the wallet's decisions at 0.0x the base rate; BTC 5m latency taker: stratified AUC 0.482 vs rotation null 0.516 (max 0.743), p=0.62; rule flags 20% of the wallet's decisions at 2.9x the base rate; the same, frozen, on 2,000+ unseen windows: stratified AUC 0.532 vs rotation null 0.498 (max 0.512), p=0.0099; rule flags 2% of the wallet's decisions at 2.3x the base rate; reviewer spot-lead score (Kraken move toward the bought side over 3 s, 1 s old): BTC 5m AUC 0.551, p=0.002, but only 6% of its fills pass the gate and it misses p<0.01 on 15m and after correcting for the hypotheses tried |
| Rule profitable in held-out PIT backtest | fail | public-data directional maker, BTC 5m strict -13.5% (5,973 fills, p(profit)=1.00); first-in-queue bound -12.8% (6,488 fills, p(profit)=1.00); BTC 15m strict -18.8% (3,057 fills, p(profit)=0.99); spot-reactive maker at 2 s, 5m strict -6.0% (266 fills, p(profit)=0.88); at-touch -4.1% (370 fills, p(profit)=0.88); 15m strict at 3 s +1.1% (179 fills, p(profit)=0.43); fixed-price resting bids (0.05-0.40, either side, no data) -81% to -45% on the same TEST windows; reviewer market-anchored, spot-gated and tape-dip makers: none significant, most lose; its own maker fills in the same windows -2.1% on 5m (p=0.65), +6.3% on 15m (p=0.35) |
| Replicable on a normal computer and connection | fail | every public-data maker version is adversely selected at the latencies a normal connection allows (>= 2 s), even with first-in-queue fills; the wallet's edge points to faster prices than public 1-second data and queue priority. Rebates are not the issue: observed taker-rebate tier Gold (18% of fees); 30-day PnL at the 0% tier $69,839, Gold $72,191, Diamond $75,587, Obsidian $76,371 |
| Conditions still hold now | pass | last 30 days p=0.0095; decline vs earlier p=0.32; last 15 vs prior 15 p=0.13; trend p=0.94 |

## Key numbers

- 30-day PnL: $72,204
- PnL at 0% rebate tier: $69,839
- Maker fill share: 92%
- Public-data maker, held out (5m / 15m): -13.5% / -18.8%
- Its own maker fills, held out (5m / 15m): -2.1% / +6.3%

## Why this verdict

- No public-data rule reproduces which passive fills it gets beyond a small association.
- Every public-data maker version loses or is insignificant in the same held-out windows, including first-in-queue bounds.
- Appears to be one operator across three wallets.

## Corrections after the adversarial review (2026-10-31)

- Its own held-out maker-fill returns changed after the tape-pagination fix (the earlier figures missed fills in dense seconds).
- The match test now uses the rotation null; results that were 'at chance' under the old null are reported with the corrected statistic.

## Evidence files

- `research/wallets/0x3725d52f3c252e8374999cc8617292ea2608ad88/profile.json`
- `research/wallets/0x3725d52f3c252e8374999cc8617292ea2608ad88/updown_study_btc_5m.json`
- `research/wallets/0x3725d52f3c252e8374999cc8617292ea2608ad88/updown_maker_study_btc_5m.json`
- `research/wallets/0x3725d52f3c252e8374999cc8617292ea2608ad88/updown_maker_study_btc_15m.json`
- `research/stage_a/updown_btc5m_maker_baselines.json`
- `research/stage_a/rebate_dependence.json`
- `research/stage_a/persistence_a1_survivors.json`
- `research/stage_a/collateral.json`
- `research/review_2026-10-31/challenge-crypto-maker-cluster/SUMMARY_all_results.json`

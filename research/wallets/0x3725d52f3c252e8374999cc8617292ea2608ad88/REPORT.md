# almach (`0x3725d52f3c252e8374999cc8617292ea2608ad88`)

Leaderboard rank 273 (monthly PnL). Verdict: **REJECT**. Archetype: Directional maker on crypto Up/Down windows (two-wallet cluster with bosona).

Profile: https://polymarket.com/profile/0x3725d52f3c252e8374999cc8617292ea2608ad88

## Mechanism

92% of sampled fills are maker fills (on-chain, 95% CI 87-95%) across BTC 5m (53%), 15m (30%), hourly and 4h Up/Down windows. Directional residual +$83.5k with a 58% win rate; locked pair spread -$23.0k. Shares bought at 0.35 win 40% of the time.

## Criteria

| Criterion | Status | Evidence |
| --- | --- | --- |
| Profit significant, not luck | pass | pre-selection 130d: HAC t=8.3, Holm p=2.6e-11, bootstrap p=2.5e-04; deflated Sharpe 1.000 |
| Net profit above $50k/month | pass | last 30d $72,204; median month $99,225 |
| Constant returns (low std) | pass | annualized Sharpe 16.8; positive weeks 86%; positive months 100% |
| High % profit | pass | peak capital at risk $5.4k; 30-day PnL $72.2k |
| Trades verified on-chain | pass | 200/200 sampled fills confirmed; 92% maker |
| Reverse-engineered rule matches the wallet | fail | directional maker: held-out AUC 0.476 (perm p=0.74) on BTC 5m, 0.457 (p=0.79) on BTC 15m; spot-latency taker: AUC 0.50 (p=0.70) |
| Rule profitable in held-out PIT backtest | fail | public-data maker on held-out windows: -17.7% (5m), -23.9% (15m), -14% to -18% with optimistic at-touch fills; almach's own maker fills +10.3% on 15m (p=0.30); the fitted taker rule +7.7% at 0 s (p=0.23) fades to +0.9% at 10 s |
| Replicable on a normal computer and connection | fail | slow makers are adversely selected at every latency tested; the edge needs queue priority and fast cancels |
| Conditions still hold now | pass | last 30 days significant (p=0.003), no decline (p=0.30); ~18% taker rebate, at 0% tier ~$70k/month |

## Key numbers

- 30-day PnL: $72,204
- Monthly ROC: 1,342% on $5.4k peak capital
- Maker fill share: 92%
- Shared tx with bosona: 6,524
- Public-data maker, held out: -17.7% (5m), -23.9% (15m)

## Why this verdict

- No public-data rule reproduces its fills (held-out AUC at chance on 5m and 15m).
- Every public-data maker version loses significantly in the same windows, even under first-in-queue fills.
- Appears to be the same operator as bosona.

## Evidence files

- `research/wallets/0x3725d52f3c252e8374999cc8617292ea2608ad88/profile.json`
- `research/wallets/0x3725d52f3c252e8374999cc8617292ea2608ad88/updown_maker_study_btc_5m.json`
- `research/wallets/0x3725d52f3c252e8374999cc8617292ea2608ad88/updown_maker_study_btc_15m.json`
- `research/wallets/0x3725d52f3c252e8374999cc8617292ea2608ad88/updown_study_btc_5m.json`
- `research/stage_a/updown_btc5m_maker_at_touch_bound.json`
- `research/stage_a/persistence_a1_survivors.json`

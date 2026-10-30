# bosona (`0xc2ad03f79ca3f3c17d8c7de2612ce0c89b7d40ed`)

Leaderboard rank 230 (monthly PnL). Verdict: **REJECT**. Archetype: Directional maker on crypto Up/Down windows (two-wallet cluster with almach).

Profile: https://polymarket.com/profile/0xc2ad03f79ca3f3c17d8c7de2612ce0c89b7d40ed

## Mechanism

94% of sampled fills are maker fills (on-chain, 95% CI 90-97%). It trades 5m (55%), 15m (28%), hourly and 4h windows, buys both sides in only 45% of markets and earns on the directional residual (+$68.8k, residual win rate 58%). Shares it buys at 0.35 win 41% of the time, at 0.14 win 19%. It shares 6,524 transactions and two-thirds of its markets with almach; 25% of their (market, second) pairs coincide.

## Criteria

| Criterion | Status | Evidence |
| --- | --- | --- |
| Profit significant, not luck | pass | pre-selection 119d: HAC t=10.6, Holm p=2.3e-16, bootstrap p=2.5e-04; deflated Sharpe 1.000 |
| Net profit above $50k/month | pass | last 30d $88,325; median month $95,161 |
| Constant returns (low std) | pass | annualized Sharpe 20.2; positive weeks 100%; positive months 100% |
| High % profit | pass | peak capital at risk $5.3k; 30-day PnL $88.3k |
| Trades verified on-chain | pass | 200/200 sampled fills confirmed; 94% maker |
| Reverse-engineered rule matches the wallet | fail | spot-model directional maker: held-out AUC 0.502 (perm p=0.30) on BTC 5m, 0.464 (p=0.75) on BTC 15m; spot-latency taker: AUC 0.48 (p=0.44); fixed-level bids: not its pattern and lose 45-81% |
| Rule profitable in held-out PIT backtest | fail | public-data maker on held-out windows: -25.6% (5m), -23.9% (15m), -14% to -18% even with optimistic at-touch fills; bosona's own maker fills there +3.5% (5m, p=0.20), +9.7% (15m, p=0.30) |
| Replicable on a normal computer and connection | fail | a slow maker is adversely selected in these markets at every latency tested (0-10 s); the wallet's edge appears to come from queue priority and fast cancels |
| Conditions still hold now | pass | last 30 days significant (p=4e-4), no decline (p=0.40); only 18% taker rebate, at 0% tier still ~$86k/month |

## Key numbers

- 30-day PnL: $88,325
- Monthly ROC: 1,665% on $5.3k peak capital
- Maker fill share: 94%
- Directional residual win rate: 58%
- Public-data maker, held out: -25.6% (5m), -23.9% (15m)
- Optimistic at-touch bound: -14% to -18%

## Why this verdict

- No public-data rule reproduces which passive fills it gets (held-out AUC at chance on 5m and 15m).
- Every public-data maker version loses significantly in the same windows, even assuming first-in-queue fills.
- Its own fills profit modestly where a slow imitator loses, which points to speed and queue position the replicator would not have.

## Evidence files

- `research/wallets/0xc2ad03f79ca3f3c17d8c7de2612ce0c89b7d40ed/profile.json`
- `research/wallets/0xc2ad03f79ca3f3c17d8c7de2612ce0c89b7d40ed/updown_maker_study_btc_5m.json`
- `research/wallets/0xc2ad03f79ca3f3c17d8c7de2612ce0c89b7d40ed/updown_maker_study_btc_15m.json`
- `research/wallets/0xc2ad03f79ca3f3c17d8c7de2612ce0c89b7d40ed/updown_study_btc_5m.json`
- `research/stage_a/updown_btc5m_maker_at_touch_bound.json`
- `research/stage_a/persistence_a1_survivors.json`

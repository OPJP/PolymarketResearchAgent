# btc5m-bot: frozen rule (iteration 1)

Code: `code/final_rule.py` (`evaluate(start_ts, end_ts) -> dict`), model files
`code/model_spot_tape_y.txt`, `code/model_spot_tape_yT.txt`, `code/model_spot_tape_yM.txt`
(LightGBM, trained only on the 1,210 most recent BUILD windows before 2026-10-16 that had tapes; nothing fitted on VALIDATE or the
holdout), helper modules `code/cells.py`, `code/tape_feats.py`, `code/spot.py`, `code/rpc.py`.

## What the rule says the bot does (mechanism as decoded so far)

1. Universe: every BTC 5-minute Up/Down window; it trades about 94% of them, all three wallets in
   the same windows. Activity only between second 2 and ~270 of the window, at prices 0.12-0.88.
2. Order type: BUY-only limit orders of a fixed share size (60 shares until 2026-10-12, then 30;
   50 on 10-17/18), priced AT THE CURRENT BEST ASK of the outcome it wants. 73% fill completely on
   arrival (taker), 13% fill partly and the remainder rests at the same price (filled within 0-2 s),
   14% rest entirely (lost the race, or a deliberate bid). It never sweeps deeper than the touch.
3. Trigger: a Binance BTCUSDT move toward that outcome in the previous ~1-3 seconds (lead-lag peak:
   fills at block-second s follow the Binance 1-s return of second s-3/s-2). The absolute level of a
   Binance fair value versus the ask is NOT the trigger (fill price - FV is centred on 0).
4. The three wallets are parallel instances on the same signal (82% of GF orders have a DS order on
   the same token within 2 s), with capital shifted between them over time.

## The frozen score

For each cell (window, outcome o, second s of the window) the presence score is
`p = model_y(features)`, features computed from public data available before s:

- Binance 1-s closes of seconds <= s-2: signed returns toward o over 1..60 s (raw and
  vol-normalised), largest favourable/adverse 1-s move in the last 3 and 10 s, 30-min sigma,
  z-score and fair value of o with the 60-s TWAP strike, seconds elapsed/remaining.
- Other traders' data-api taker prints with block ts <= s-1 (cluster wallets' own prints and every
  print in a transaction where a cluster order was the maker are removed): last implied ask and bid
  of o and their ages, last price, VWAP 10/30 s, print counts 1/2/5/30 s, signed flow toward o,
  30-s volume, Binance move since the last print, fair-value minus market gaps, implied spread.
- No own-state features (no inventory, no own fill counts or times).

A cell is flagged when `p >= 0.30`. The rule's predicted side in a second is the outcome with the
higher score; its predicted price for a taker fill is the last implied ask of that outcome.

## VALIDATE metrics (2026-10-16..23, chosen and reported on VALIDATE only)

| metric | VALIDATE | target |
|---|---|---|
| presence AUC, any fill, no own-state (PRIMARY) | **0.892** | >= 0.85 (met) |
| presence AUC taker / maker | 0.893 / 0.867 | |
| presence AUC WITH own state (inventory; secondary, not the frozen rule) | 0.906 | |
| presence AUC per wallet GF / XM / DS | 0.888 / 0.902 / 0.880 | |
| at p >= 0.30: recall / lift / flagged share | 55.8% / 3.81 / 14.6% (p~0) | |
| side accuracy (seconds with a one-sided buy) | 66.3% vs favourite 45.9%, tape-flow 52.5% (McNemar p~0) | >= 80% (not met) |
| taker price within one tick of last implied ask | 49.2% (exact 25.7%) | |
| selection AUC among all taker prints (pooled / within window) | 0.692 / 0.679; recall 62.9% at lift 1.64 | >= 0.80 (not met) |
| per-window PnL correlation (crude proxy) | 0.305 (Spearman 0.256) | >= 0.5 (not met) |
| ablation: without 1-2 s tape activity/age features | 0.831 | |
| ablation: market-only (tape + rel/tau, no Binance) | 0.878 | |
| spot-only model (14-day BUILD) | 0.805 | |

Files: `results_tape_model.json`, `results_validate_metrics.json`, `results_spot_model.json`,
`results_ablation.json`.

## Known limitations

- The outcome metric uses a crude PnL proxy (buy 30 shares at the last observed ask when flagged),
  not a strict-fill backtest.
- Selection AUC is pooled (no rotation null) in iteration 1.
- Tape features need data-api tapes; windows without a tape get NaN tape features.

"""Iteration 10 (late): the side row and the why-it-works paragraph of FINAL_RULE.md get the rung-class result."""
from pathlib import Path

p = Path(__file__).resolve().parents[1] / "FINAL_RULE.md"
s = p.read_text(encoding="utf-8")
a = s.index("**Iteration 10 (A1): this is not a stable rule of the engine's history.**")
b = s.index("Imbalance pairing bids (11-14% of lot fills) sit on the under-held outcome 100% (own state).")
new = ("**Iteration 10 (A1 + rung classes): it is the side rule of the US-session 500 ladder, and it replicates historically.** With "
       "pre-registered historical proxies (match clock = taker signing ms + 620 ms clipped to [block - 3 s, block - 1.5 s], the real "
       "Chainlink value from the crypto-price endpoint, the last clean print at block - 3 s) that reproduce the 10-31 truth (0.953 vs "
       "0.965), the lot's 500-share rungs buy the Chainlink favourite where it disagrees with the market 0.973 (VALIDATE aggregate, 73 "
       "fills in 26 windows) and 0.759 (STUDY, 11 windows); the off-session 62/250 rungs (00-12 UTC: 62/250 are 80% of the fills there) "
       "do not (0.46-0.53) and follow no public candidate (cheaper side, favourite, Binance or Chainlink posture 0.48-0.51 on STUDY), so "
       "over all lot fills region D is only 0.66-0.68 (10-31 00-06: 0.679). A class-conditional public rule failed its pre-registered "
       "VALIDATE test (0.660 vs 0.710, gain -0.049 [-0.085, -0.017]). ")
s = s[:a] + new + s[b:]
s = s.replace("| VALIDATE-only (live 10-31); fails the historical replication on the lot (A1) |",
              "| VALIDATE-only (500 ladder: live 10-31 and historical VALIDATE region D); hypothesis (off-session 62/250 ladder: no decoded side) |")
s = s.replace("but the strong\nform seen on 10-31 is not the engine's stable behaviour (A1), and",
              "and on the\nhistorical VALIDATE its US-session 500 rungs follow the report where it disagrees with the market 97% of the time\n(A1), while its off-session 62/250 ladder shows no skew; and")
p.write_text(s, encoding="utf-8")
print("ok")

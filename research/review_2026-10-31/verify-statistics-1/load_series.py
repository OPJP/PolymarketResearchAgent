"""Load the exact cached user-pnl bodies used by stage A1 (read-only sqlite),
verify each body's sha256 against stage_a1.json, and rebuild the daily
pre-selection series exactly as polyrea.workflows.screen.wallet_pnl_metrics does.
Writes series.npz (pickled dict) to this directory."""
import hashlib, json, pickle, sqlite3, sys, zlib
from pathlib import Path

REPO = Path("/home/user/PolymarketResearchAgent")
sys.path.insert(0, str(REPO))
from polyrea.analysis.pnl import daily_frame  # noqa: E402

OUT = Path(__file__).resolve().parent
a1 = json.load(open(REPO / "research/stage_a/stage_a1.json"))
as_of = a1["evidence"]["subject"]["as_of"]
db = sqlite3.connect(f"file:{REPO/'.cache/http.sqlite'}?mode=ro", uri=True)

res = {}
mism = 0
for r in a1["wallets"]:
    src = r["metrics"].get("source") or {}
    url = src.get("url")
    if not url:
        continue
    key = hashlib.sha256(f"GET {url} ".encode()).hexdigest()
    row = db.execute("SELECT fetched_at, body FROM responses WHERE key=?", (key,)).fetchone()
    if row is None:
        print("missing", r["wallet"]); continue
    raw = zlib.decompress(row[1])
    if hashlib.sha256(raw).hexdigest() != src.get("body_sha256"):
        mism += 1
    body = (json.loads(raw) or {}).get("data") or {}
    df = daily_frame(body.get("points") or [], as_of=as_of)
    if df.empty or "d_economic_pnl" not in df:
        continue
    d = df["d_economic_pnl"].iloc[1:].to_numpy(float)
    n = len(d)
    pre = d[: max(0, n - 30)]
    res[r["wallet"]] = {"name": r["name"], "rank": r["rank"], "full": d, "pre": pre}
print(f"as_of={as_of} loaded={len(res)} sha_mismatch={mism}")
pickle.dump({"as_of": as_of, "series": res, "order": [r["wallet"] for r in a1["wallets"]]}, open(OUT / "series.pkl", "wb"))

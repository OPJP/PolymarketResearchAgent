"""Iteration 8 continuation of the EXAM-INPUT recorder (catalog X46 = panel-information iter7 P3, X57 = panel-assumptions
iter7 P4). rec_exam7.py stops at 11-02 06:00 UTC, before any weekday sealed block. This launcher sleeps until --start and
then runs rec_exam7's recorder unchanged (same feeds, same parsing, same Writer filing) under the feed names
btc5m_xclob8 / btc5m_xven8 (REC7_SUFFIX = "8"; status .cache/re/btc5m-bot/rec_exam78.status) until --stop, with its own
disk cap (REC7_DISK_CAP_MB, default 290 here). Weekday sealed blocks covered if it runs to 11-03 18:00: 11-02 06-12,
11-02 18-24, 11-03 00-06, 11-03 12-18 (development: 11-02 12-18, 11-03 06-12). final_rule._live_vote reads both name sets.
Usage: python rec_exam8.py --start 1793599140 --stop 1793728800"""
import os, sys, time, json, asyncio, argparse

os.environ.setdefault("REC7_SUFFIX", "8")
os.environ.setdefault("REC7_DISK_CAP_MB", "290")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", type=float, required=True)
    ap.add_argument("--stop", type=float, required=True)
    a = ap.parse_args()
    while time.time() < a.start:
        time.sleep(min(60.0, max(0.5, a.start - time.time())))
    import rec_exam7  # noqa: E402  (reads REC7_SUFFIX at import)
    rec_exam7.ST["launcher"] = "rec_exam8"
    asyncio.run(rec_exam7.main(a.stop))
    print(json.dumps(rec_exam7.ST)[:2000])

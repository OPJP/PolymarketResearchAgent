"""Iteration 9 state.json addendum: finding 14 (add level leads the public book), X24 closed, final minutes."""
import json
from pathlib import Path
ROOT = Path(__file__).resolve().parents[5]
P = ROOT / "research/reverse_engineering/tommy-cs2-maker/state.json"
s = json.loads(P.read_text(encoding="utf-8"))
cat = s["catalog"]
r = json.load(open(ROOT / "research/reverse_engineering/tommy-cs2-maker/results/add_level_info.json"))
cat["X124"]["evidence"] += (" | Uncensored follow-up (add_level_info.json, BUILD-live): Spearman(own add offset from the others' mid, others'-mid move) "
    f"{r['h2s']['own_spearman']} / {r['h10s']['own_spearman']} / {r['h30s']['own_spearman']} at 2 / 10 / 30 s (other makers' adds {r['h2s']['other_spearman']} / {r['h10s']['other_spearman']} / {r['h30s']['other_spearman']}; time-shift null ~0); "
    f"untriggered own adds (no own take within -1..+3 s, no public trade in the 2 s before) 10 s {r['subsets_10s']['untriggered']['own_spearman_10s']} vs others {r['subsets_10s']['untriggered']['other_spearman_10s']}: its quote level leads the public mid.")
cat["X24"] = {"status": "tried", "source": cat["X24"].get("source", "information panel P6 (iter 2)"),
              "evidence": cat["X24"]["evidence"] + " | Closed (iterations 8-9): with the feed's own takes as anchors the Dota offset is found (finding 24 of iteration 8: D 1035-1050 s on four maps, side-label null p < 0.005-0.07; P4e-only within 2 s), and it was used for X123 (game-state V anchor, rejected), X119 (maker bursts vs kills, weak) and X129 (lag spread)."}
s["hypotheses"].append({"id": "H106", "family": "price", "description": "The wallet's maker quote LEVEL carries a private value that leads the public book (uncensored adds).",
    "validate_metrics": {"own_spearman_2_10_30s": [r["h2s"]["own_spearman"], r["h10s"]["own_spearman"], r["h30s"]["own_spearman"]],
                         "other_spearman_2_10_30s": [r["h2s"]["other_spearman"], r["h10s"]["other_spearman"], r["h30s"]["other_spearman"]],
                         "untriggered_own_10s": r["subsets_10s"]["untriggered"]["own_spearman_10s"], "untriggered_other_10s": r["subsets_10s"]["untriggered"]["other_spearman_10s"]},
    "verdict": "supported (BUILD-live, one block; quote-follower confound possible at 2 s); pre-registered for VALIDATE-live"})
comp = s["components"]
comp["price"]["description"] += (" Uncensored adds (BUILD-live): its add level relative to the others' mid predicts the others' mid move (Spearman 0.44 at 10 s, untriggered 0.38) vs 0.17 / 0.15 for other makers: the level is an informed private value that leads the public book.")
P.write_text(json.dumps(s, indent=1), encoding="utf-8")
op = [k for k, v in s["catalog"].items() if v.get("status") == "open"]
print("open", len(op), op)

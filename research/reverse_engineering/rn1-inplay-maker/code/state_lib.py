"""Builds and updates state.json (the brief's format, 2026-11-01)."""
from __future__ import annotations

import json
from pathlib import Path

R = Path(__file__).resolve().parents[1]
F = R / "state.json"

CATALOG_IDS = (["A1", "A2", "A3", "A4", "A4b", "A5", "A5a", "A6", "A6b", "A7", "A8"]
               + [f"B{i}" for i in range(1, 10)]
               + ["C1", "C2", "C3", "C4", "C4b", "C5", "C6", "C7", "C8"]
               + ["D1", "D2", "D3", "D4"] + [f"E{i}" for i in range(1, 8)] + ["X1", "X2"])

TARGET_KEYS = ["presence_auc", "selection_auc", "selection_recall", "selection_lift", "presence_baseline",
               "selection_baseline", "side_accuracy", "side_baseline", "price_within_tick", "pnl_corr_pearson",
               "pnl_corr_spearman", "coverage_fills", "coverage_abs_pnl"]


def load() -> dict:
    return json.load(open(F)) if F.exists() else {}


def save(s: dict) -> None:
    json.dump(s, open(F, "w"), indent=1, default=str)


def set_catalog(s: dict, cid: str, status: str, evidence: str) -> None:
    s.setdefault("catalog", {})[cid] = {"status": status, "evidence": evidence}


def set_dim(s: dict, name: str, **kw) -> None:
    d = s.setdefault("dimensions", {}).setdefault(name, {})
    d.update(kw)

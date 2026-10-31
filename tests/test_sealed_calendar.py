"""The pre-registered sealed calendar used by the deep reverse engineering (research/reverse_engineering/tools/sealed.py)."""
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("sealed", ROOT / "research" / "reverse_engineering" / "tools" / "sealed.py")
sealed = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sealed)

H, T0, DAY, BLOCK = sealed.H, sealed.T0, sealed.DAY, sealed.BLOCK


def test_historical_lots_alternate_days():
    assert sealed.lot_of(H - 1) == "dev"
    assert [sealed.lot_of(H + d * DAY + 3600) for d in range(8)] == ["h1", "h2"] * 4
    assert sealed.lot_of(T0 - 1) == "h2"  # 2026-10-30, the forward day after as_of


def test_future_blocks_rotate_time_of_day():
    day0 = [sealed.future_block_sealed(T0 + j * BLOCK) for j in range(4)]
    day1 = [sealed.future_block_sealed(T0 + DAY + j * BLOCK) for j in range(4)]
    assert day0 == [False, True, False, True]
    assert day1 == [True, False, True, False]
    assert sealed.block_bounds(T0 + BLOCK + 10) == (T0 + BLOCK, T0 + 2 * BLOCK)


def test_release_and_next_lot(tmp_path, monkeypatch):
    monkeypatch.setattr(sealed, "BASE", tmp_path)
    key = "s"
    assert sealed.is_sealed(H + 10, key) and not sealed.is_sealed(H - 10, key)
    lot = sealed.next_lot(key, T0 + 3 * DAY)
    assert lot["lot"] == "h1" and lot["sealed_hours"] == 96
    sealed.release(key, "h1")
    assert not sealed.is_sealed(H + 10, key) and sealed.is_sealed(H + DAY + 10, key)
    assert sealed.next_lot(key, T0 + 3 * DAY)["lot"] == "h2"
    sealed.release(key, "h2")
    # Future lot: sealed blocks that ended since the last future exam. 12:00 on day 1 -> blocks 06-12 and 18-24 of
    # day 0 and 00-06 of day 1 are sealed and over.
    lot = sealed.next_lot(key, T0 + DAY + 12 * 3600)
    assert lot["lot"] == "f" and lot["sealed_hours"] == 18 and lot["until"] == T0 + DAY + BLOCK
    sealed.release(key, "f", until=lot["until"])
    assert not sealed.is_sealed(T0 + BLOCK + 10, key)
    assert sealed.is_sealed(T0 + DAY + 2 * BLOCK + 10, key)
    assert json.loads((tmp_path / key / "results" / "sealed_state.json").read_text())["released"] == ["h1", "h2"]


def test_intervals_merge_and_handle_fractional_ends(tmp_path, monkeypatch):
    monkeypatch.setattr(sealed, "BASE", tmp_path)
    dev = sealed.intervals("s", H - DAY, T0 + DAY + 0.5, sealed=False)
    assert dev[0] == (H - DAY, H)
    assert (T0, T0 + BLOCK) in dev and (T0 + 2 * BLOCK, T0 + 3 * BLOCK) in dev
    sl = sealed.intervals("s", H, T0 + 0.7, sealed=True)
    assert sl == [(H, T0)]

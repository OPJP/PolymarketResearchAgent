"""Evidence envelope shared by every polyrea tool.

Mirrors REA's result contract: requested facts are returned inline together
with their provenance (sources), coverage, limitations and unknowns. Observed
facts (straight from a source), derived facts (deterministic computation over
observed facts) and inferred facts (hypotheses, interpretations, verdicts) are
kept in separate sections so a consumer never mistakes an inference for an
observation. Missing coverage is reported as unknown, never as absence.
"""

from __future__ import annotations

import dataclasses
import datetime as dt
import hashlib
import json
import math
from typing import Any, Literal

import numpy as np

CoverageStatus = Literal["complete", "partial", "unknown", "empty"]


@dataclasses.dataclass
class Source:
    """One upstream read that contributed to a result."""

    adapter: str
    url: str
    fetched_at: str
    records: int | None = None
    body_sha256: str | None = None
    cached: bool = False


@dataclasses.dataclass
class Coverage:
    status: CoverageStatus
    detail: str = ""

    def __post_init__(self) -> None:
        if self.status not in ("complete", "partial", "unknown", "empty"):
            raise ValueError(f"invalid coverage status {self.status!r}")


@dataclasses.dataclass
class Evidence:
    """Result contract for every tool.

    ``observed`` holds facts read from a source, ``derived`` deterministic
    computations over them, ``inferred`` interpretations that can be wrong.
    """

    tool: str
    subject: dict[str, Any]
    observed: dict[str, Any] = dataclasses.field(default_factory=dict)
    derived: dict[str, Any] = dataclasses.field(default_factory=dict)
    inferred: dict[str, Any] = dataclasses.field(default_factory=dict)
    sources: list[Source] = dataclasses.field(default_factory=list)
    coverage: Coverage = dataclasses.field(default_factory=lambda: Coverage("unknown"))
    limitations: list[str] = dataclasses.field(default_factory=list)
    unknowns: list[str] = dataclasses.field(default_factory=list)
    next_probes: list[str] = dataclasses.field(default_factory=list)
    generated_at: str = dataclasses.field(default_factory=lambda: utc_now_iso())

    def to_dict(self) -> dict[str, Any]:
        return to_jsonable(dataclasses.asdict(self))

    def to_json(self, **kwargs: Any) -> str:
        return json.dumps(self.to_dict(), **kwargs)

    def digest(self) -> str:
        """Stable digest of the analytical content (excludes timestamps)."""
        payload = self.to_dict()
        payload.pop("generated_at", None)
        payload["sources"] = [
            {k: v for k, v in s.items() if k != "fetched_at"} for s in payload["sources"]
        ]
        return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()


def utc_now_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()


def to_jsonable(value: Any) -> Any:
    """Convert numpy / pandas / dataclass values to strict JSON values.

    Non-finite floats become ``None`` because JSON has no NaN/Infinity and an
    unknown value must not be serialized as a number.
    """
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        return to_jsonable(dataclasses.asdict(value))
    if isinstance(value, dict):
        return {str(k): to_jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [to_jsonable(v) for v in value]
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating, float)):
        f = float(value)
        return f if math.isfinite(f) else None
    if isinstance(value, np.bool_):
        return bool(value)
    if isinstance(value, np.ndarray):
        return [to_jsonable(v) for v in value.tolist()]
    if isinstance(value, (dt.datetime, dt.date)):
        return value.isoformat()
    if hasattr(value, "isoformat") and callable(value.isoformat):  # pandas Timestamp
        return value.isoformat()
    return value

"""Auris sherpa-512 second-pass identity: name a diarized speaker from the gallery, gated.

Zero-confident-wrong: a diarized speaker is named ONLY when its best gallery match
clears ALL THREE AS-norm gate conditions; otherwise it stays UNKNOWN. Naming is the
sole job of sherpa-512 here — diarization labels stay anonymous (SPEAKER_XX), and a
below-gate match never writes a speaker_id.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.services.speaker_asnorm import score_asnorm


@dataclass(frozen=True)
class IdentityMatch:
    """Outcome of gating one diarized speaker against the gallery."""
    name: str | None          # gallery name when gated; None means UNKNOWN
    raw_cosine: float
    asnorm_score: float | None
    gated: bool
    reason: str               # why it was/wasn't named (audit trail)


def distance_to_cosine(distance: float) -> float:
    """sqlite-vec stores unit vectors; Euclidean distance d gives cosine = 1 - d^2/2."""
    return 1.0 - (float(distance) ** 2) / 2.0


def candidates_from_gallery(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Convert store.search_speaker_vectors rows (rowid,name,distance,...) to scored candidates."""
    scored = [
        {"name": row.get("name"), "cosine": distance_to_cosine(row["distance"])}
        for row in rows
        if row.get("name")
    ]
    scored.sort(key=lambda c: c["cosine"], reverse=True)
    return scored


def decide_identity(
    candidates: list[dict[str, Any]],
    *,
    cosine_floor: float | None = None,
    asnorm_floor: float | None = None,
    margin_floor: float | None = None,
) -> IdentityMatch:
    """Gate the best gallery candidate. Name it ONLY when raw cosine >= cosine_floor AND
    the AS-norm z-score >= asnorm_floor AND the margin >= margin_floor. Thresholds default
    to the production policy when not overridden."""
    if cosine_floor is None or asnorm_floor is None or margin_floor is None:
        # Lazy: only the production path needs the policy module; callers passing
        # explicit floors (e.g. tests) stay free of the wider app import graph.
        from app.services.speaker_match_policy import (
            asnorm_margin_threshold,
            asnorm_threshold,
            name_assignment_threshold,
        )
        cosine_floor = name_assignment_threshold() if cosine_floor is None else cosine_floor
        asnorm_floor = asnorm_threshold() if asnorm_floor is None else asnorm_floor
        margin_floor = asnorm_margin_threshold() if margin_floor is None else margin_floor

    if not candidates:
        return IdentityMatch(None, 0.0, None, False, "no_candidates")
    top = candidates[0]
    raw = float(top["cosine"])
    cohort = [float(c["cosine"]) for c in candidates[1:]]

    if raw < cosine_floor:
        return IdentityMatch(None, raw, None, False, "below_cosine_floor")
    asn = score_asnorm(raw, cohort)
    if asn is None:
        # Too few impostors to AS-normalize — cosine alone is not enough to name.
        return IdentityMatch(None, raw, None, False, "no_cohort")
    if asn.score < asnorm_floor:
        return IdentityMatch(None, raw, asn.score, False, "below_asnorm")
    if asn.margin is None or asn.margin < margin_floor:
        return IdentityMatch(None, raw, asn.score, False, "below_margin")
    return IdentityMatch(top["name"], raw, asn.score, True, "gated")

"""Suggest identities for diarized speakers from their sherpa-512 centroids via the gallery.

The engine already extracts one 512-d centroid per diarized speaker. This gates each centroid
against the canonical SQLite speaker gallery and, ONLY when the match clears the AS-norm gate,
records it as a *suggestion* (suggested_name + linked profile + confidence) for the user to
confirm. It never sets display_name or verified — a gated match is a strong hint, not a silent
rename. Below-gate speakers are left untouched (zero-confident-wrong).

Pure orchestration: the gallery search and the per-speaker write are injected, so the Celery
postprocess supplies live implementations and this stays unit-testable.
"""
from __future__ import annotations

from typing import Any, Callable

from app.services.auris_identity import candidates_from_gallery, decide_identity


def assign_native_identities(
    db_embeddings: dict[int, Any],
    *,
    search: Callable[[list[float]], list[dict[str, Any]]],
    floors: dict[str, float],
    set_suggestion: Callable[[int, str, float, int | None], None],
) -> dict[str, Any]:
    """Gate each speaker's 512-d centroid against the gallery; suggest ONLY when gated.

    db_embeddings: {speaker_id: 512-d vector}. search(vector) -> gallery rows
    (name/profile_id/distance). set_suggestion(speaker_id, name, cosine, profile_id) records
    the confirmable suggestion. Below-gate speakers are skipped — never a confident-wrong name.
    """
    suggested: list[dict[str, Any]] = []
    unknown: list[dict[str, Any]] = []
    for speaker_id, vector in db_embeddings.items():
        rows = search(list(vector))
        match = decide_identity(candidates_from_gallery(rows), **floors)
        if match.gated and match.name:
            profile_id = next(
                (r.get("profile_id") for r in rows
                 if r.get("name") == match.name and r.get("profile_id")),
                None,
            )
            set_suggestion(speaker_id, match.name, match.raw_cosine, profile_id)
            suggested.append({
                "speaker_id": speaker_id,
                "name": match.name,
                "cosine": round(match.raw_cosine, 4),
                "profile_id": profile_id,
            })
        else:
            unknown.append({"speaker_id": speaker_id, "reason": match.reason})
    return {"suggested": suggested, "unknown": unknown, "total": len(db_embeddings)}

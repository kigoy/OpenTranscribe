"""Name anonymous diarized speakers via the Auris sherpa-512 gallery gate.

The pipeline already creates one anonymous Speaker (display_name=None) per SPEAKER_XX
cluster. This second pass NAMES a Speaker (sets display_name) ONLY when its gallery
match clears the gate; below-gate speakers stay anonymous (UNKNOWN). Pure orchestration —
the embed, gallery search, and name-write are injected, so the Celery task supplies the
live implementations and this stays unit-testable.
"""
from __future__ import annotations

from typing import Any, Callable

from app.services.auris_identity import IdentityMatch, candidates_from_gallery, decide_identity


def resolve_identity(audio_path: str, gallery_conn, *, extractor, store, floors: dict | None = None) -> IdentityMatch:
    """Embed one speaker's representative audio and gate it against the SQLite gallery."""
    vector = extractor.embed_file(audio_path)
    rows = store.search_speaker_vectors(gallery_conn, list(vector), limit=8)
    return decide_identity(candidates_from_gallery(rows), **(floors or {}))


def run_identity_assignment(
    speakers: list[dict[str, Any]],
    resolve: Callable[[dict[str, Any]], IdentityMatch],
    set_display_name: Callable[[Any, str], None],
) -> dict[str, Any]:
    """For each anonymous speaker, resolve identity and name it ONLY if gated.

    speakers: [{"id": <speaker_id>, "audio": <path>}, ...].
    resolve(speaker) -> IdentityMatch; set_display_name(speaker_id, name) writes the name.
    Below-gate speakers are left untouched (UNKNOWN) — never a confident-wrong name.
    """
    named: list[dict[str, Any]] = []
    unknown: list[dict[str, Any]] = []
    for speaker in speakers:
        match = resolve(speaker)
        if match.gated and match.name:
            set_display_name(speaker["id"], match.name)
            named.append({"id": speaker["id"], "name": match.name, "cosine": round(match.raw_cosine, 4)})
        else:
            unknown.append({"id": speaker["id"], "reason": match.reason})
    return {"named": named, "unknown": unknown, "total": len(speakers)}

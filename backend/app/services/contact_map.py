"""CONTACT_MAP authority — maps a speaker name to an Apple contact.

Category rules (the file is the name-to-identity source of truth):
- contact: links to a real Apple contact via apple_uid.
- variant: a misspelled/alias name; routes to its canonical (renamed_to) + apple_uid.
- non_contact: a real person with no Apple contact — first-class, never auto-merged.
- junk: not a person — never linked, never named.
fuzzy-confidence and variant resolutions are human-review grade, never auto-applied as exact.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

_DEFAULT_PATH = "/Volumes/Extreme Pro/auris/data/speakers/CONTACT_MAP.json"
_LINKABLE_CATEGORIES = ("contact", "variant")


@dataclass(frozen=True)
class ContactResolution:
    """How one speaker name resolves against the CONTACT_MAP."""
    name: str
    category: str            # contact | non_contact | junk | variant
    confidence: str          # exact | fuzzy | none
    canonical_name: str | None   # match (contact) or renamed_to (variant); None when not linkable
    apple_uid: str | None
    linkable: bool           # has a real apple_uid AND a linkable category
    needs_review: bool       # fuzzy/variant — surface to a human, do not auto-apply as exact


class ContactMap:
    """In-memory CONTACT_MAP with category-honoring resolution."""

    def __init__(self, entries: dict[str, Any]):
        self._entries = entries

    @classmethod
    def load(cls, path: str | Path | None = None) -> "ContactMap":
        """Load the JSON map. Path precedence: arg > CONTACT_MAP_PATH env > default."""
        resolved = Path(path or os.getenv("CONTACT_MAP_PATH") or _DEFAULT_PATH).expanduser()
        return cls(json.loads(resolved.read_text()))

    def __len__(self) -> int:
        return len(self._entries)

    def resolve(self, name: str) -> ContactResolution | None:
        """Resolve a speaker name; None if the name is absent from the map."""
        entry = self._entries.get(name)
        if entry is None:
            return None
        category = str(entry.get("category") or "junk")
        confidence = str(entry.get("confidence") or "none")
        apple_uid = entry.get("apple_uid")
        # variant routes to its canonical (renamed_to); contact uses its match.
        canonical = entry.get("renamed_to") or entry.get("match")
        # junk / non_contact have no apple_uid and must never be auto-merged to a contact.
        linkable = bool(apple_uid) and category in _LINKABLE_CATEGORIES
        needs_review = confidence == "fuzzy" or category == "variant"
        return ContactResolution(
            name=name,
            category=category,
            confidence=confidence,
            canonical_name=canonical if linkable else None,
            apple_uid=apple_uid if linkable else None,
            linkable=linkable,
            needs_review=needs_review,
        )

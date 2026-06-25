"""One-way Apple Contacts → OpenTranscribe profile alignment (read-only, idempotent).

Rules
-----
- A profile name *aligns* only when resolve() returns linkable=True AND its
  apple_uid is in the caller-supplied live_contact_uids set.
- variant resolutions route to canonical_name and are also flagged needs_review.
- fuzzy-confidence resolutions are linkable but also flagged needs_review.
- junk / non_contact / absent names → unmatched.
- A uid present in the map but absent from live_contact_uids → unmatched.
- NO DB writes, NO Apple write-back, NO network calls.  Pure function.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .contact_map import ContactMap


def align_profiles(
    profile_names: list[str],
    contact_map: "ContactMap",
    live_contact_uids: set[str],
) -> dict:
    """Align profile names against the contact map and a live uid set.

    Parameters
    ----------
    profile_names:
        Speaker / profile names as stored in OpenTranscribe.
    contact_map:
        A loaded ContactMap instance (provides .resolve(name)).
    live_contact_uids:
        The set of apple_uid values currently present in the live Address Book.
        Used to guard against stale map entries pointing at deleted contacts.

    Returns
    -------
    dict with three keys:
        aligned      – list[dict] each with {name, apple_uid, canonical_name}
        needs_review – list[dict] same shape; subset of aligned requiring human check
        unmatched    – list[str]  names with no valid live-contact link
    """
    aligned: list[dict] = []
    needs_review: list[dict] = []
    unmatched: list[str] = []

    for name in profile_names:
        resolution = contact_map.resolve(name)

        if resolution is None:
            unmatched.append(name)
            continue

        if not resolution.linkable:
            # junk / non_contact — never linked
            unmatched.append(name)
            continue

        if resolution.apple_uid not in live_contact_uids:
            # map entry exists but contact was deleted from the live book
            unmatched.append(name)
            continue

        # name aligns to a live contact
        entry = {
            "name": name,
            "apple_uid": resolution.apple_uid,
            "canonical_name": resolution.canonical_name,
        }
        aligned.append(entry)

        if resolution.needs_review:
            needs_review.append(entry)

    return {
        "aligned": aligned,
        "needs_review": needs_review,
        "unmatched": unmatched,
    }

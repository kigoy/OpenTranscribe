#!/usr/bin/env python3
"""Surface the sherpa-512 gallery names into OT SpeakerProfiles so /speakers shows them.

Reads the SQLite gallery (speaker_vec_meta) and upserts one SpeakerProfile per gallery
name for the owning user, then back-links each gallery row to its OT profile_id. Name-only:
the SQLite gallery stays the embedding authority; these profiles are the UI registry the
owner validates. Idempotent — re-running only adds missing names.
"""
from __future__ import annotations

import json
import os
import sqlite3
import sys

SQLITE = os.path.expanduser(os.getenv("GALLERY_SQLITE", "~/.opentranscribe/search/search.sqlite3"))
USER_ID = int(os.getenv("GALLERY_OWNER_USER_ID", "2"))


def main() -> int:
    from app.db.base import SessionLocal
    from app.models.media import SpeakerProfile

    gallery = sqlite3.connect(SQLITE)
    rows = gallery.execute(
        "SELECT rowid, name FROM speaker_vec_meta WHERE name IS NOT NULL AND TRIM(name) != ''"
    ).fetchall()

    rowid_to_pid: dict[int, int] = {}
    created = existing = 0
    db = SessionLocal()
    try:
        for rowid, name in rows:
            profile = db.query(SpeakerProfile).filter_by(user_id=USER_ID, name=name).one_or_none()
            if profile is None:
                profile = SpeakerProfile(user_id=USER_ID, name=name, voice_calibration_source="sherpa-gallery")
                db.add(profile)
                db.flush()
                created += 1
            else:
                existing += 1
            rowid_to_pid[int(rowid)] = int(profile.id)
        db.commit()
    finally:
        db.close()

    for rowid, pid in rowid_to_pid.items():
        gallery.execute("UPDATE speaker_vec_meta SET profile_id = ? WHERE rowid = ?", (pid, rowid))
    gallery.commit()
    gallery.close()

    json.dump(
        {"gallery_names": len(rows), "profiles_created": created, "profiles_existing": existing,
         "linked": len(rowid_to_pid), "user_id": USER_ID},
        sys.stdout, indent=2,
    )
    print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Unit tests for filename-derived creation_date parsing.

Re-downloaded recordings (HiNotes mp3s, HiDock `.hda` exports) carry no embedded
CreateDate, so the recording date survives only in the filename. The parser must
recover it without letting arbitrary digit runs masquerade as dates.
"""

import datetime
from types import SimpleNamespace

import pytest

from app.tasks.transcription.metadata_extractor import (
    _try_parse_creation_date_from_filename,
)

UTC = datetime.timezone.utc


def _mf(filename, creation_date=None):
    return SimpleNamespace(filename=filename, creation_date=creation_date)


@pytest.mark.parametrize(
    "filename,expected",
    [
        # ISO date prefix (the common HiNotes title form)
        ("2025-06-09 Funding Arrangement Discussion.mp3", datetime.datetime(2025, 6, 9, tzinfo=UTC)),
        # HiDock export stem carries a full timestamp
        ("20260626-214143-Rec22.hda", datetime.datetime(2026, 6, 26, 21, 41, 43, tzinfo=UTC)),
        # date embedded mid-name, with a non-date suffix
        ("2026-01-19_Strategic-Partnership_seg9.wav", datetime.datetime(2026, 1, 19, tzinfo=UTC)),
        # month-only falls to the first of the month
        ("2025-06 Monthly Sync.mp3", datetime.datetime(2025, 6, 1, tzinfo=UTC)),
    ],
)
def test_parses_real_date_forms(filename, expected):
    mf = _mf(filename)
    _try_parse_creation_date_from_filename(mf)
    assert mf.creation_date == expected


@pytest.mark.parametrize(
    "filename",
    [
        "2023 Document Review and DoD Contract.mp3",  # bare year — too imprecise, leave to fallback
        "July 2nd Personal Updates.mp3",  # no numeric date
        "Meeting-12345678-notes.mp3",  # 8 digits but not a timestamp
        "2025-13-40 impossible date.mp3",  # out-of-range month/day
        "recording.mp3",  # nothing
    ],
)
def test_skips_when_no_in_range_date(filename):
    mf = _mf(filename)
    _try_parse_creation_date_from_filename(mf)
    assert mf.creation_date is None


def test_does_not_override_existing_date():
    existing = datetime.datetime(2020, 1, 1, tzinfo=UTC)
    mf = _mf("2025-06-09 Later Meeting.mp3", creation_date=existing)
    _try_parse_creation_date_from_filename(mf)
    assert mf.creation_date == existing  # embedded metadata already won


def test_full_date_beats_month_when_both_present():
    mf = _mf("2025-06-09 sync.mp3")
    _try_parse_creation_date_from_filename(mf)
    assert mf.creation_date == datetime.datetime(2025, 6, 9, tzinfo=UTC)

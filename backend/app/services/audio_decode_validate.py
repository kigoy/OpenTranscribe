"""Audio decode validation: probe a local file for playback-readiness via ffprobe.

Returns a plain dict — no side effects, no DB writes, no transcoding.
The ``probe`` parameter is injectable so callers can substitute a fake in tests.
"""
from __future__ import annotations

import json
import logging
import shutil
import subprocess
from typing import Any, Callable

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Default probe (shells out to ffprobe)
# ---------------------------------------------------------------------------

def _default_probe(path: str) -> dict[str, Any]:
    """Run ffprobe against *path* and return parsed JSON.

    Raises:
        RuntimeError: when ffprobe is not on PATH, exits non-zero, or returns
            unparseable output.
    """
    ffprobe_path = shutil.which("ffprobe")
    if not ffprobe_path:
        raise RuntimeError("ffprobe binary not found on PATH")

    try:
        proc = subprocess.run(  # noqa: S603  # nosec B603
            [
                ffprobe_path,
                "-v", "error",
                "-show_streams",
                "-show_format",
                "-of", "json",
                path,
            ],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
    except (subprocess.SubprocessError, FileNotFoundError) as exc:
        raise RuntimeError(f"ffprobe subprocess failed: {exc}") from exc

    if proc.returncode != 0:
        stderr = proc.stderr[:300] if proc.stderr else ""
        raise RuntimeError(
            f"ffprobe exited {proc.returncode}: {stderr}"
        )

    if not proc.stdout:
        raise RuntimeError("ffprobe produced no output")

    try:
        return json.loads(proc.stdout)  # type: ignore[no-any-return]
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"ffprobe JSON decode failed: {exc}") from exc


# ---------------------------------------------------------------------------
# Public surface
# ---------------------------------------------------------------------------

def validate_audio(
    path: str,
    *,
    max_duration_s: float = 3600.0,
    probe: Callable[[str], dict[str, Any]] = _default_probe,
) -> dict[str, Any]:
    """Validate that *path* is a decodable audio file.

    Args:
        path: Filesystem path to the audio file.
        max_duration_s: Warn (``over_cap=True``) but do not fail when duration
            exceeds this value.  Defaults to one hour.
        probe: Callable ``(path) -> dict`` returning ffprobe JSON.  Swap for a
            fake in tests — the real implementation never runs under test.

    Returns:
        A dict with keys:

        - ``ok`` (bool): True when a decodable audio stream with positive
          duration was found.
        - ``codec`` (str | None): Audio codec name from the first audio stream.
        - ``duration_s`` (float | None): Duration in seconds from ffprobe
          format data.
        - ``over_cap`` (bool): True when ``duration_s > max_duration_s``.
          Surfaced for the caller to handle; ``ok`` stays True.
        - ``error`` (str | None): Human-readable reason when ``ok`` is False.
    """
    result: dict[str, Any] = {
        "ok": False,
        "codec": None,
        "duration_s": None,
        "over_cap": False,
        "error": None,
    }

    try:
        data = probe(path)
    except Exception as exc:  # noqa: BLE001
        logger.debug("audio probe failed for %s: %s", path, exc)
        result["error"] = str(exc)
        return result

    return _interpret(data, max_duration_s, result)


# ---------------------------------------------------------------------------
# Internals
# ---------------------------------------------------------------------------

def _interpret(
    data: dict[str, Any],
    max_duration_s: float,
    result: dict[str, Any],
) -> dict[str, Any]:
    """Interpret ffprobe JSON into the validate_audio result dict (in-place)."""
    streams = data.get("streams") or []
    audio_stream = next(
        (s for s in streams if s.get("codec_type") == "audio"), None
    )

    if audio_stream is None:
        result["error"] = "no audio stream found"
        return result

    result["codec"] = audio_stream.get("codec_name")

    # Duration: prefer format-level value (more reliable than stream-level)
    fmt = data.get("format") or {}
    raw_duration = fmt.get("duration") or audio_stream.get("duration")
    if raw_duration is None:
        result["error"] = "duration not reported by ffprobe"
        return result

    try:
        duration_s = float(raw_duration)
    except (TypeError, ValueError):
        result["error"] = f"duration not parseable: {raw_duration!r}"
        return result

    if duration_s <= 0:
        result["error"] = f"non-positive duration: {duration_s}"
        return result

    result["duration_s"] = duration_s
    result["over_cap"] = duration_s > max_duration_s
    result["ok"] = True
    return result

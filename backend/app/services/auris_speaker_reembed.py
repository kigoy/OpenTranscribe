"""Re-embed diarized speakers with the canonical sherpa-512 extractor for gallery gating.

The diarizer's native centroids are 256-d (pyannote/wespeaker) — correct for in-file speaker
clustering but NON-interoperable with the canonical sherpa-3dspeaker (512-d) gallery. To gate a
diarized speaker against that gallery it must be embedded with the SAME model. This slices each
speaker's diarized audio out of the decoded WAV and computes one 512-d sherpa embedding per
speaker. The extractor is injected so this stays unit-testable without the onnx model.
"""
from __future__ import annotations

from typing import Any, Callable

import numpy as np

# Below this much speech a centroid is too unstable to gate on — skip the speaker.
MIN_SPEECH_SECONDS = 0.6


def embed_speakers_sherpa512(
    wav_path: str,
    speaker_windows: dict[int, list[tuple[float, float]]],
    extractor: Any,
    *,
    max_seconds: float = 30.0,
    read_audio: Callable[[str], tuple[np.ndarray, int]] | None = None,
) -> dict[int, np.ndarray]:
    """Return {speaker_id: 512-d sherpa embedding} for speakers with enough speech.

    wav_path: decoded mono WAV. speaker_windows: {speaker_id: [(start_s, end_s), ...]}.
    extractor.compute(samples, sample_rate) -> 512-d. Speakers with < MIN_SPEECH_SECONDS of
    usable audio, or whose embedding fails, are simply omitted (never raises per-speaker).
    """
    samples, sr = (read_audio or _read_wav)(wav_path)
    samples = _as_mono_float32(samples)

    out: dict[int, np.ndarray] = {}
    for speaker_id, windows in speaker_windows.items():
        chunks: list[np.ndarray] = []
        total = 0.0
        for start, end in sorted(windows):
            if end <= start:
                continue
            a = max(0, int(start * sr))
            b = min(len(samples), int(end * sr))
            if b <= a:
                continue
            chunks.append(samples[a:b])
            total += (b - a) / sr
            if total >= max_seconds:
                break
        if not chunks or total < MIN_SPEECH_SECONDS:
            continue
        audio = np.concatenate(chunks) if len(chunks) > 1 else chunks[0]
        try:
            out[speaker_id] = np.asarray(extractor.compute(audio, sr), dtype=np.float32)
        except Exception:
            continue
    return out


def _read_wav(path: str) -> tuple[np.ndarray, int]:
    import soundfile as sf

    samples, sample_rate = sf.read(path, dtype="float32", always_2d=False)
    return np.asarray(samples, dtype=np.float32), int(sample_rate)


def _as_mono_float32(samples: np.ndarray) -> np.ndarray:
    audio = np.asarray(samples, dtype=np.float32)
    if audio.ndim > 1:
        audio = audio.mean(axis=1)
    return np.ascontiguousarray(audio, dtype=np.float32)

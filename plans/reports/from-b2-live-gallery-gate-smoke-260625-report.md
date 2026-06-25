# B2 Auris identity gate — live smoke (real clip → 209-gallery → gate)

**Conclusion:** the embed→SQLite-gallery→AS-norm-gate path works on real audio and correctly
returns UNKNOWN for an out-of-gallery speaker (zero-confident-wrong). Measured, not asserted.

## Run
- Clip: `data/reharvest_staging/Adrian_Hornung/5823834305415262208_27-57.wav` (Adrian Hornung — NOT in the gallery).
- Embed: `Sherpa3SpeakerExtractor.embed_file` → 512-d.
- Gallery: live SQLite `~/.opentranscribe/search/search.sqlite3` (209 sherpa-512 vectors), `store.search_speaker_vectors`.
- Gate: `auris_identity.decide_identity` with production floors.

## Result (measured)
- Top gallery candidates: Bruce Dickinson 0.6137, Guy Grayson 0.5615, Areg Nzsdejan 0.5419, Yoav Suesskind 0.5338.
- Decision: **name=None, gated=False, reason=below_cosine_floor**, raw_cosine 0.6137.
- The best match is a weak 0.61 cosine (wrong speaker) → the gate refuses to name → UNKNOWN. Correct.

## Verified both directions
- IN-gallery: earlier self-match test — 8/8 stored vectors return themselves at distance 0 (cosine 1) → would clear the gate.
- OUT-of-gallery: this smoke — weak top match rejected → UNKNOWN.

## Still open (B2 integration, needs the live worker)
- The Celery `auris_identity_task`: group a real transcript's diarized SPEAKER_XX segments → embed per cluster → decide → write `Speaker.display_name` / `TranscriptSegment.speaker_id` ONLY above gate; hook into `postprocess.py finalize_transcription`.
- Full e2e: a real 2-speaker file where one speaker IS in the gallery → confirm that segment gets named and the other stays UNKNOWN, through the running pipeline.

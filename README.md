# heritage_short

## Pipeline setup

Create an environment with `python3 -m venv .venv`, then install dependencies with
`.venv/bin/python -m pip install -r requirements.txt`.
Set `GEMINI_API_KEY` in the ignored `.env` file before running the live smoke test.
The smoke test checks Gemini text and speech generation and appends call results to
`runs.jsonl`.

Run `make validate` to validate `storyboard.json`, or `make smoke` to exercise the
Gemini APIs. `make narration` generates one Amharic TTS WAV per shot in
`outputs/narration/`, using input-hash caching and fitting small duration overruns
with pitch-preserving speed adjustment; it rejects clips that exceed the fit cap.
`make radio-cut` generates any missing narration, then assembles
`outputs/radio_cut.mp4` with a black screen and a quiet synthetic placeholder
music bed. Both targets require `ffmpeg` and `ffprobe` on `PATH`.
Narration requests are spaced 20 seconds apart by default for the Gemini free
tier; set `GEMINI_TTS_MIN_INTERVAL_SEC` in `.env` to override the interval.
The provider also enforces daily quotas; completed shot WAVs are cached so a run
can resume after quota resets without regenerating successful clips.

The `keyframes`, `shots`, `music`, `assemble`, and `film` stages still need
media-processing implementations.


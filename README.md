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
`make reference-sheet` creates a local illustrated character sheet at
`outputs/refs/character_sheet.png`; `make keyframes` renders one 16:9 local
illustration per storyboard shot; `make shots` applies a slow FFmpeg camera move
to each still. These are deterministic vector-style placeholders, not
model-generated footage, and incur no API usage.
`make music` creates a deterministic synthetic score in `outputs/music/` from
the storyboard tempo, key, and duration. `make assemble` combines the moving
shots, narration, and score into two subtitled exports: `outputs/film.mp4`
(16:9) and `outputs/film_9x16.mp4` (9:16). The closing three-second visual AI
disclosure extends the 75 seconds of shots to a 78-second film; music continues
under the card, and the score is ducked beneath narration. `make film` runs that
full pipeline. `make radio-cut` generates any missing narration and assembles
`outputs/radio_cut.mp4` with a black screen and the local score; the radio cut
remains 75 seconds. The media targets require `ffmpeg` and `ffprobe` on `PATH`,
with FFmpeg built with the `subtitles` filter and Noto Sans Ethiopic available
through fontconfig. English subtitle cues are distributed proportionally across
each Amharic narration clip's measured duration; review their alignment during
the final edit.
Narration requests are spaced 20 seconds apart by default for the Gemini free
tier; set `GEMINI_TTS_MIN_INTERVAL_SEC` in `.env` to override the interval.
The provider also enforces daily quotas; completed shot WAVs are cached so a run
can resume after quota resets without regenerating successful clips.

Reference sheets, keyframes, moving shots, and music use input-hash caching in
`.cache/`; generated media is kept under the ignored `outputs/` directory.

## Assignment evidence

See [ARCHITECTURE.md](./ARCHITECTURE.md) for the stage map, [DESIGN.md](./DESIGN.md)
for the creative decisions and radio-cut feedback, [EXPERIMENTS.md](./EXPERIMENTS.md)
for measured findings, [COSTS.md](./COSTS.md) for API usage and cost limitations,
[ETHICS.md](./ETHICS.md) for consent/privacy/disclosure notes, and
[AUDIENCE_TEST.md](./AUDIENCE_TEST.md) for the near-final screening record and
the still-pending qualitative feedback.


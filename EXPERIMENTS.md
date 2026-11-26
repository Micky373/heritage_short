# Experiments and measured findings

## 2026-11-26: Gemini availability and latency

**Question:** Are the configured Gemini text and TTS models usable for this
pipeline, and how long do the recorded calls take?

**Method:** Summarized the 31 logical call records in `runs.jsonl`. Retries are
inside each logged operation, so the latency measures the wrapper call rather
than individual network attempts.

**Result:** `gemini-2.5-flash` produced three errors, including the documented
404 model-not-found failure. `gemini-3.8-flash` produced four errors in this
snapshot; earlier records and `FAILURES.md` describe deadline/high-demand
responses. `gemini-3.8-flash-tts` produced 19 successes and five errors in 24
records. Median and p95 latencies, plus the missing cost estimates, are listed
in `COSTS.md`.

**Interpretation:** Text availability was not reliable in this snapshot.
Successful TTS calls show that TTS was usable at least some of the time, not
that quota or availability is guaranteed. Cached narration makes interrupted
runs resumable.

## 2026-11-26: local rendering and timing checks

**Question:** Can the local pipeline produce the requested aspect ratios and
preserve the storyboard timings without regenerating cached source assets?

**Method:** Ran `make validate`, the subtitle unit tests, `make assemble`, and
`make radio-cut`; inspected the rendered media metadata with ffprobe.

**Result:** The storyboard validates. The film exports are 1280×720 and
720×1280, each 78 seconds including the three-second end card. The radio cut
remains 75 seconds. All nine narration clips, keyframes, moving shots, and the
local score were reused from cache during the assembly run.

**Limitations:** English subtitle cues are distributed proportionally across
the measured Amharic narration clip duration; they are not forced-aligned to
English speech. Review subtitle timing and both crops by watching the exports.
The vector keyframes and synthetic score are deterministic placeholders, not
model-generated footage or a recorded krar/piano score.

**Visual spot-check:** Inspected representative frames from both aspect ratios:
the first-shot subtitles were visible, the portrait crop retained both walking
characters, and the English/Amharic end-card text was centered and legible. This
is a technical spot-check, not audience feedback or a substitute for watching
the full film.

## Audience evidence and next experiments

`DESIGN.md` records qualitative feedback from three listeners on the radio cut.
The user reports screening both near-final aspect ratios with three viewers on
2026-11-26. They said all three felt strongly connected to the story because of
their shared background, with the same reaction to both formats. Their
constructive suggestions were more natural-looking images and actual moving
video rather than camera motion over stills. No post-screening changes were
reported; see `DESIGN.md` and `AUDIENCE_TEST.md`.

No controlled visual-model or music-model comparison has been run. After an
approved provider, budget, and asset rights are established, compare candidate
visual and music workflows using the same storyboard prompts and seeds; record
model/version, settings, latency, cost source, licensing, and human ratings.

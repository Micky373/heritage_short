# Architecture

## Pipeline

`storyboard.json` is the project contract. Each stage validates it against
`schema/storyboard.schema.json` before processing. The `Makefile` exposes the
stages and their dependencies:

```text
make film
  narration ─┐
  shots ─────┼─> assemble ─> outputs/film.mp4 (16:9)
  music ─────┘             └> outputs/film_9x16.mp4 (9:16)

make radio-cut
  narration ─┐
  music ─────┴─> radio_cut ─> outputs/radio_cut.mp4
```

`make film` is the normal end-to-end command. It expects Python dependencies,
FFmpeg, ffprobe, subtitle-filter support, and a Gemini API key: the current
narration stage initializes its client before checking cached clips.
`make radio-cut` produces the 75-second black-screen listening cut. The
finished film adds the storyboard's three-second visual AI disclosure card, so
its target runtime is 78 seconds.

## Stage boundaries

| Stage | Implementation | Inputs and outputs |
| --- | --- | --- |
| Contract | `pipeline/utils.py` and the JSON Schema | Validates storyboard data before stages run. |
| Narration | `pipeline/narration.py` | Calls Gemini TTS for Amharic speech; checks/fits clips to shot durations. |
| Reference sheet and keyframes | `pipeline/visuals.py` | Renders deterministic SVG illustrations to local PNGs. |
| Moving shots | `pipeline/visuals.py` | Uses FFmpeg to pan/zoom the still keyframes; these are not generated video. |
| Score | `pipeline/music.py` | Synthesizes a deterministic local placeholder score from storyboard metadata. |
| Film assembly | `pipeline/assemble.py` | Adds English subtitles, crops to both ratios, appends the AI card, ducks score under narration, and checks runtime. |
| Radio cut | `pipeline/radio_cut.py` | Mixes narration and local score over black at 16:9. |
| Smoke test | `pipeline/smoke_test.py` | Exercises Gemini text and TTS connectivity; not needed to render cached/local stages. |

The local illustrations and score do not make model requests and are
placeholders. Gemini is currently used for narration and the optional smoke
test, not for image, video, or music generation.

## Caching, calls, and outputs

Stage caches in `.cache/pipeline_cache.json` use SHA-256 hashes of the relevant
inputs. Per-shot narration, keyframe, and moving-shot stages can therefore
reuse unchanged outputs. API calls are retried with bounded delays and recorded
in append-only `runs.jsonl`; failures and operational notes are kept in
`FAILURES.md`.

Generated media and the local cache are under ignored `outputs/` and `.cache/`
directories. They are not included in a source checkout. A clean run needs the
Python dependencies from `requirements.txt`, FFmpeg/ffprobe with the required
filters and fonts, and a Gemini credential for uncached narration. Keep that
credential in the ignored `.env` file and do not put it in logs or documentation.

## Clean-clone workflow

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
# Add GEMINI_API_KEY to the local, ignored .env file.
make validate
make film
```

To run the unit tests, use:

```sh
.venv/bin/python -m unittest discover -s tests -v
```

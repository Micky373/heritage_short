# heritage_short

## Pipeline setup

Create an environment with `python3 -m venv .venv`, then install dependencies with
`.venv/bin/python -m pip install -r requirements.txt`.
Set `GEMINI_API_KEY` in the ignored `.env` file before running the live smoke test.
The smoke test checks Gemini text and speech generation and appends call results to
`runs.jsonl`.

Run `make validate` to validate `storyboard.json`, or `make smoke` to exercise the
Gemini APIs. The `narration`, `radio-cut`, `keyframes`, `shots`, `music`, `assemble`,
and `film` targets validate the storyboard; their media-processing stages still
need implementations.


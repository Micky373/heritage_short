# Morning Steps with my father

A 78-second heritage short about the morning walks, conversations, and small
habits that connect childhood learning with a later career in data science.

The film uses Gemini-generated Amharic narration, English subtitles, locally
rendered illustrated stills, and a synthetic placeholder score. The stills are
not model-generated footage, and the score is not a recorded instrument
performance.

## Film outputs

| Output | Format | Runtime | Includes |
| --- | --- | ---: | --- |
| `outputs/film.mp4` | 16:9 | 78 sec | Moving illustrated shots, Amharic narration, English subtitles, score, AI disclosure end card |
| `outputs/film_9x16.mp4` | 9:16 | 78 sec | Portrait version of the same film |
| `outputs/radio_cut.mp4` | 16:9 black screen | 75 sec | Amharic narration and score |

The built media is tracked in `outputs/` and available for direct download.
The film adds a three-second visual AI disclosure card after the 75 seconds
of storyboard shots. The radio cut stays at 75 seconds.

## Run it locally

### 1. Install the tools

You need Python 3.10 or later, Git, Make, FFmpeg, ffprobe, and Noto Sans
Ethiopic. FFmpeg must include its `subtitles` filter (libass).

Check your FFmpeg and font setup:

```sh
ffmpeg -hide_banner -filters | grep subtitles
ffprobe -version
fc-match "Noto Sans Ethiopic"
```

The `fc-match` check is for Linux; on macOS or Windows, confirm the font is
installed using the system font manager.
Install FFmpeg, Make, and the Noto Ethiopic font through your operating
system's package manager if any of those checks fail.

### 2. Clone and install Python dependencies

```sh
git clone https://github.com/Micky373/heritage_short.git
cd heritage_short
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
```

These commands are for Linux/macOS shells. On Windows, use WSL for the same
workflow; native Windows needs a Make-compatible shell and interpreter-path
adjustments.

### 3. Add your local Gemini key

Create a `.env` file in the repository root and add your Gemini API key:

```dotenv
GEMINI_API_KEY=your_key_here
```

Optional model and voice overrides:

```dotenv
GEMINI_TEXT_MODEL=gemini-3.8-flash
GEMINI_TTS_MODEL=gemini-3.8-flash-tts
GEMINI_TTS_VOICE=Kore
GEMINI_TTS_MIN_INTERVAL_SEC=20
```

`.env` is ignored by Git. Never commit or include the key in an issue, log
excerpt, screenshot, or support request.

### 4. Validate and build

```sh
make validate
make film
```

The first film build generates narration through Gemini and may be subject to
account quotas or API charges. Unchanged narration and local stages are cached
to help later runs resume without repeating completed work.

To try the radio cut instead:

```sh
make radio-cut
```

### Create a new Amharic story

After installing dependencies and adding `GEMINI_API_KEY`, run:

```sh
make create-story
```

The command asks for a title and an Amharic story, generates a complete
storyboard, validates it, saves the previous storyboard as
`storyboard.previous.json`, and runs `make film`.

For automation or to keep long stories in a text file:

```sh
.venv/bin/python -m pipeline.create_story \
  --title "My Story" \
  --story-file story.txt \
  --shots 9 \
  --duration 78
```

Use `--no-build` to generate and validate the storyboard without building the
film. A custom storyboard replaces `storyboard.json`, and the previous version
is retained as `storyboard.previous.json`.

## Useful commands

| Command | What it does | Gemini API call? |
| --- | --- | --- |
| `make validate` | Validate `storyboard.json` against its schema | No |
| `make create-story` | Generate a custom Amharic storyboard, validate it, and build the film | Yes |
| `make smoke` | Test Gemini text and TTS connectivity; append results to `runs.jsonl` | Yes |
| `make narration` | Generate/cache one Amharic narration clip per shot | Yes, if narration is uncached |
| `make reference-sheet` | Render the local character reference sheet | No |
| `make keyframes` | Render local illustrated shot frames | No |
| `make shots` | Add slow FFmpeg camera moves to the stills | No |
| `make music` | Create the local synthetic placeholder score | No |
| `make assemble` | Build both subtitled film exports | Yes, if narration is uncached |
| `make radio-cut` | Build the 75-second black-screen cut | Yes, if narration is uncached |
| `make film` | Run the complete film pipeline | Yes, if narration is uncached |

Run the focused tests with:

```sh
.venv/bin/python -m unittest discover -s tests -v
```

## Notes before sharing

- TTS calls are paced to reduce free-tier rate-limit errors, but provider quotas
  and availability can still interrupt a run. Completed shots are cached.
- English subtitle cues are distributed proportionally across each measured
  Amharic narration clip; they are not forced-aligned. Review timing before
  publishing.
- `runs.jsonl` is tracked and contains request parameters, including narration
  text. Review it for private content before sharing the repository.
- See [FAILURES.md](./FAILURES.md) for known issues and recorded fixes.

## Report a problem or suggest an improvement

Issues and feature requests are welcome on the
[GitHub Issues page](https://github.com/Micky373/heritage_short/issues/new).
Please include the command you ran, your operating system, Python/FFmpeg
versions, what you expected, and a sanitized error excerpt. Do **not** attach
`.env`, API keys, tokens, or narration text you do not want to share.

## Project documentation

| Document | What it covers |
| --- | --- |
| [ARCHITECTURE.md](./ARCHITECTURE.md) | Pipeline stages and clean-clone workflow |
| [DESIGN.md](./DESIGN.md) | Creative decisions and audience-test feedback |
| [EXPERIMENTS.md](./EXPERIMENTS.md) | Measured results and limitations |
| [COSTS.md](./COSTS.md) | API call counts and cost-accounting limits |
| [ETHICS.md](./ETHICS.md) | Consent, privacy, disclosure, and asset provenance |
| [AUDIENCE_TEST.md](./AUDIENCE_TEST.md) | Near-final screening record and feedback |

## Assignment reports

The [`reports/`](./reports/) folder contains the assignment document and
submitted report PDF(s).

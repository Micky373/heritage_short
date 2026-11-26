# Failure log

## Gemini text: `gemini-2.5-flash` returned `404 NOT_FOUND`

- **Symptom:** A Gemini text-generation request using `gemini-2.5-flash` returned
  `404 NOT_FOUND` because the requested model could not be resolved by the API.
- **Root cause:** The configured model ID was unavailable to the request's API
  endpoint or account.
- **Fix:** Switched the text model configuration to `gemini-3.8-flash`. Set
  `GEMINI_TEXT_MODEL=gemini-3.8-flash` in `.env` to make the selection explicit.
  Run `make smoke` to verify access with the current credentials.

## Gemini smoke test appeared to hang without progress

- **Symptom:** `make smoke` could sit silently while waiting for a Gemini request;
  progress was only printed after the request completed.
- **What the run log showed:** Existing calls completed in about 0.6–4.4 seconds,
  with errors and one successful TTS call. The recorded calls do not show a
  multi-minute request, so the silence was consistent with missing progress
  output rather than a confirmed long-running call.
- **Fast diagnostic:** With the bounded settings, the text request returned
  `503 UNAVAILABLE` after two attempts (about 14.5 seconds total); the TTS call
  succeeded in about 4.2 seconds. The provider reported high demand, so the
  current text-call failure is service availability rather than an indefinite
  hang.
- **Cause:** The Gemini SDK request timeout was unset, its default retry policy
  allows five attempts with exponential delays, and the smoke wrapper also
  retried API errors up to three times. This could multiply the wait on
  transient failures, while output gave no indication of an active request.
- **Fix:** Set a 10-second SDK request timeout and disable SDK-level retries.
  The smoke wrapper now makes at most two attempts with a 0.5-second initial
  backoff, and retries only transient API statuses. It flushes progress before
  each request attempt so a stalled request is visible.

## `504 DEADLINE_EXCEEDED` during Gemini text smoke test

- **Symptom:** `text-smoke` using `gemini-3.8-flash` returned
  `504 DEADLINE_EXCEEDED`, while `tts-smoke` using
  `gemini-3.8-flash-tts` succeeded.
- **Cause observed:** The text-generation request hit a deadline. The reported
  504 does not identify whether the deadline was enforced by the API or client;
  the separate TTS call completed successfully.
- **Adjustment:** Increased the text request timeout to 30 seconds, kept the
  TTS timeout at 10 seconds, and raised the retry pause to 1 second. The smoke
  test still makes at most two attempts and prints the configured timeout before
  each stage, with flushed attempt progress.

## Initial dual-aspect film assembly failed in the audio filter graph

- **Symptom:** `make assemble` stopped on the 9:16 export with an FFmpeg
  `Stream specifier 'voiceext' ... matches no streams` error.
- **Cause:** The filter graph connected the same filtered narration output to
  both the sidechain compressor and final audio mixer without splitting it.
- **Fix:** Split the extended narration stream into separate program and
  sidechain inputs before ducking the score. Re-running `make assemble` should
  reuse all cached narration, keyframes, moving shots, and music.


## Text timeout increase exposed temporary high demand

- **Observation:** Raising the `gemini-3.8-flash` text timeout to `30000 ms`
  resolved the earlier `504 DEADLINE_EXCEEDED`; the subsequent text smoke call
  reported a temporary `503 UNAVAILABLE` due to high demand.
- **TTS status:** `gemini-3.8-flash-tts` remained healthy and generated audio.
- **Action:** Keep the 30-second text timeout and the bounded retry/backoff
  behavior; retry the text smoke test after service demand subsides.

## Narration generation stopped at the Gemini TTS daily quota

- **Symptom:** `make radio-cut` generated and cached narration for eight shots,
  then failed on `shot_09` with HTTP `429`; the provider reported a free-tier
  limit of 10 TTS requests per day. Since narration was incomplete, the radio
  cut was not assembled.
- **Cause:** The Gemini TTS daily request quota was exhausted before all nine
  storyboard shots had audio.
- **Resolution:** Wait for the provider quota to reset, then rerun
  `make radio-cut`. Existing validated shot WAVs are cached, so the run resumes
  from the missing narration instead of regenerating completed shots.

## Radio-cut rerun still blocked by TTS daily quota

- **Symptom:** A rerun of `make radio-cut` reused the eight cached narration
  clips, then received HTTP `429` while generating `shot_09`. The provider
  reported approximately 23 hours and 35 minutes until the daily quota resets.
- **Cause:** The Gemini TTS free-tier daily allowance was still exhausted, so
  the missing ninth clip could not be generated and the MP4 was not assembled.
- **Next step:** Retry `make radio-cut` after the quota reset; the eight existing
  clips remain cached and should not be requested again.

## Updated Gemini credentials allowed the final narration request

- **Finding:** With the updated environment credentials, TTS returned audio for
  `shot_09`, but its initial 8.19-second duration exceeded the 7-second shot
  allocation and the previous 1.15x speed-fit cap, so validation rejected it.
- **Fix:** Raised the pitch-preserving speed-fit cap to 1.20x and reran the
  missing narration. The final clip fit at 6.97 seconds; all nine clips then
  assembled successfully into the 75-second `outputs/radio_cut.mp4`.

## Shot 09 closing narration initially exceeded its duration

- **Symptom:** After adding the AI disclosure, the first `shot_09` TTS read was
  9.42 seconds for a 7-second slot. The duration guard rejected it, and the
  existing clip was not replaced.
- **Fix:** Shortened both language versions and changed the closing delivery
  from slow to gently brisk. The regenerated narration is 4.76 seconds; all
  other shot clips were reused from cache and the 75-second radio cut rebuilt.

## Amharic AI wording exceeded the closing shot on first generation

- **Symptom:** The revised `shot_09` narration with Latin `AI` generated
  9.42 seconds of speech for a 7-second shot and failed the duration check.
- **Fix:** Spelled the acronym in Amharic as `ኤአይ` and kept the concise
  disclosure. The regenerated narration is 4.67 seconds; shots 01–08 were
  reused from cache and the 75-second radio cut was rebuilt.

## Local `slow_pan` motion render failed on an undefined FFmpeg variable

- **Symptom:** `make shots` rendered the first three clips, then FFmpeg failed
  for `shot_04` with an undefined `d` expression in the `zoompan` filter.
- **Cause and fix:** The filter expression referenced `d`, which is not a
  supported `zoompan` expression variable. The pan and tilt coordinates now
  use the known output frame count as their denominator; rerunning the stage
  reuses already-rendered clips and retries the failed shot.


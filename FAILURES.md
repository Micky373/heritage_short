# Failure log

## Gemini text: `gemini-2.5-flash` returned `404 NOT_FOUND`

- **Symptom:** A Gemini text-generation request using `gemini-2.5-flash` returned
  `404 NOT_FOUND` because the requested model could not be resolved by the API.
- **Root cause:** The configured model ID was unavailable to the request's API
  endpoint or account.
- **Fix:** Switched the text model configuration to `gemini-3.8-flash`. Set
  `GEMINI_TEXT_MODEL=gemini-3.8-flash` in `.env` to make the selection explicit.
  Run `make smoke` to verify access with the current credentials.

No API keys or tokens are recorded here. `.env` remains excluded by `.gitignore`.

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

No API keys or tokens are recorded here; `.env` remains ignored.

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

No API keys or tokens are recorded in this entry.

## Text timeout increase exposed temporary high demand

- **Observation:** Raising the `gemini-3.8-flash` text timeout to `30000 ms`
  resolved the earlier `504 DEADLINE_EXCEEDED`; the subsequent text smoke call
  reported a temporary `503 UNAVAILABLE` due to high demand.
- **TTS status:** `gemini-3.8-flash-tts` remained healthy and generated audio.
- **Action:** Keep the 30-second text timeout and the bounded retry/backoff
  behavior; retry the text smoke test after service demand subsides.

No API keys or tokens are recorded in this entry.
"""Exercise Gemini text and speech generation and log both API calls."""

from __future__ import annotations

import base64
import os
import sys
from typing import Any

from dotenv import load_dotenv
from google import genai
from google.genai.errors import APIError

from pipeline.utils import (
    ROOT,
    retry_api_call,
    run_logged_call,
    validate_storyboard,
)

TEST_SENTENCE = "ሰላም፣ ዛሬ ጥሩ ቀን ነው።"
TEXT_PROMPT = f"Reply with this exact Amharic sentence and nothing else: {TEST_SENTENCE}"


def _make_text_call(client: genai.Client, model: str) -> str:
    response = retry_api_call(
        lambda: client.models.generate_content(model=model, contents=TEXT_PROMPT),
        retryable_exceptions=(APIError,),
    )
    text = response.text
    if not text or not text.strip():
        raise RuntimeError("Gemini text response was empty")
    return text.strip()


def _make_tts_call(client: genai.Client, model: str, voice: str) -> bytes:
    interaction: Any = retry_api_call(
        lambda: client.interactions.create(
            model=model,
            input=[
                {
                    "type": "user_input",
                    "content": [{"type": "text", "text": TEST_SENTENCE}],
                }
            ],
            response_format={"type": "audio"},
            generation_config={"speech_config": [{"voice": voice}]},
        ),
        retryable_exceptions=(APIError,),
    )
    audio_data = interaction.output_audio.data
    audio = base64.b64decode(audio_data, validate=True)
    if not audio:
        raise RuntimeError("Gemini TTS response contained no audio")
    return audio


def main() -> int:
    load_dotenv(ROOT / ".env")
    validate_storyboard()
    text_model = os.getenv("GEMINI_TEXT_MODEL", "gemini-2.5-flash")
    tts_model = os.getenv("GEMINI_TTS_MODEL", "gemini-3.8-flash-tts")
    voice = os.getenv("GEMINI_TTS_VOICE", "Kore")

    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        print(
            "GEMINI_API_KEY is missing; set it in .env or the environment.",
            file=sys.stderr,
        )
        return 2

    client = genai.Client(
        api_key=api_key,
        http_options={"api_version": "v1beta"},
    )
    failures: list[tuple[str, Exception]] = []

    calls = (
        (
            "text-smoke",
            text_model,
            {"prompt": TEXT_PROMPT},
            lambda: _make_text_call(client, text_model),
        ),
        (
            "tts-smoke",
            tts_model,
            {"text": TEST_SENTENCE, "voice": voice},
            lambda: _make_tts_call(client, tts_model, voice),
        ),
    )
    for stage, model, parameters, operation in calls:
        try:
            result = run_logged_call(
                operation,
                stage=stage,
                shot_id=None,
                model=model,
                parameters=parameters,
                cost_usd_est=None,
            )
            if stage == "text-smoke":
                print(f"Gemini text response: {result}")
            else:
                print(f"Gemini TTS generated {len(result)} audio bytes.")
        except Exception as error:
            failures.append((stage, error))
            print(f"{stage} failed: {error}", file=sys.stderr)

    if failures:
        print(
            f"{len(failures)} Gemini smoke call(s) failed; see runs.jsonl.",
            file=sys.stderr,
        )
        return 1
    print("Both Gemini smoke calls succeeded; see runs.jsonl.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

# Ethics, consent, and provenance

## Story and permission

The film is based on my own childhood memories of walking and learning with my
father in Sidist Kilo. My father gave his full permission for our shared story to
be adapted and included in this film.

No real person appears in the video. The father, child, and adult figures are
locally rendered illustrations; they are not photographs, recordings, or
likenesses of real people. The story is personal to me and is not intended to
represent every Ethiopian family or the wider Sidist Kilo community.

## Use of AI

Gemini TTS generated the Amharic narration from the story and narration text I
wrote. The voice is a synthetic preset, not a recording or clone of my father's
or another real person's voice. The film discloses AI use in the spoken closing
narration and in an English/Amharic end card.

The English subtitles come from the English narration text in the storyboard.
Their cues are distributed proportionally across the measured Amharic audio
duration, rather than aligned through word-level transcription. This is a
technical timing limitation, not a claim of exact translation or
transcription.

The character sheet and shot illustrations are deterministic vector artwork
rendered by the local pipeline. FFmpeg animates those still images with camera
moves; they are not AI-generated video. The score is a deterministic synthetic
placeholder, not a recording of krar, piano, or other instruments.

## Audience feedback

The radio-cut feedback is summarized anonymously in `DESIGN.md`. On
2026-11-26, three viewers saw both the 16:9 and 9:16 near-final versions. They
reported feeling strongly connected to the story because they shared a similar
background; the same reaction was reported for both formats. The summary
contains no names, recordings, or individual ratings.

## Data and credentials

The Gemini API key is kept in the local `.env` file, which is excluded by
`.gitignore`. No key or token is included in this document. The tracked
`runs.jsonl` records model-call parameters, including narration text. It
contains project content and is handled separately from credentials.

## Sources and limitations

The illustrations and placeholder score were created by the project's local
code; no stock footage or commercial music recording was used. Gemini
generation is subject to the provider's applicable terms. Noto Sans Ethiopic
is used through the system font installation for text rendering; the font file
is not bundled with the project.

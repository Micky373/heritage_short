## Audience Test #1 (Radio Cut — `outputs/radio_cut.mp4`)

* **Participants:** Tamirie Andualem (Father), Hirut Bazezew (Mother), H/Gabriel Tamirie (Brother)
* **Format:** 75-second radio cut (`outputs/radio_cut.mp4`) featuring the 9-shot Amharic narration track, ambient/placeholder backing, and closing AI disclosure on `shot_09`.

### Listener Takeaways
* **Tamirie Andualem (Father):** Highlighted the emotional resonance of the Six Kilo morning walks, English/math practice on the move, and how those early habits carry into current data work; suggested smoothing brief pauses between shots and giving the closing AI statement a clean, unhurried finish.
* **Hirut Bazezew (Mother):** Praised the warm, grounded tone and personal growth arc from early morning routines to international confidence; recommended keeping mid-cut pacing tight so the link to data science stays effortless to follow.
* **H/Gabriel Tamirie (Brother):** Noted strong narrative focus and a clear bridge from everyday reasoning to data and code; suggested keeping inter-shot gaps brisk while preserving the clear closing AI disclosure.

### Storyboard & Cut Notes (`storyboard.json`)
* Confirmed `shot_09` retains explicit AI disclosure (`"ይህ ፊልም በኤአይ ተዘጋጅቷል።"`) within its timing window without crowding the closing takeaway.
* Flagged inter-shot silence/pacing and visual-audio alignment as key tuning points for **Step 4** (reference sheet, keyframes, moving shots, and score).

## Step 4 implementation

The free/local path is now wired through `make reference-sheet`, `make keyframes`,
`make shots`, `make music`, and `make assemble` (or `make film`). The reference
sheet and 16:9 shot frames are deterministic SVG illustrations derived from the
storyboard, and FFmpeg adds the requested camera moves as slow pans/zooms.
The score is a deterministic synthetic pentatonic bed; it is a placeholder, not
a model-generated krar/piano recording. These stages use input-hash caching and
do not make Gemini requests. Generated assets stay under ignored `outputs/`.

The nine rendered clips and the assembled 75-second film were checked against
the storyboard timing. The Amharic narration, including `shot_09`'s AI
disclosure, remains unchanged; `make radio-cut` continues to provide the
black-screen version with the same local score. The vector artwork and synthetic
score are production placeholders; replace them with approved generated or
recorded assets before treating the visuals or music as final.
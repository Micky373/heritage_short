PYTHON ?= $(if $(wildcard .venv/bin/python),.venv/bin/python,python3)

.PHONY: validate smoke narration radio-cut reference-sheet keyframes shots music assemble film

validate:
	$(PYTHON) -m pipeline.utils validate

smoke:
	$(PYTHON) -m pipeline.smoke_test

narration:
	$(PYTHON) -m pipeline.narration

radio-cut: narration music
	$(PYTHON) -m pipeline.radio_cut

reference-sheet:
	$(PYTHON) -m pipeline.visuals reference-sheet

keyframes: reference-sheet
	$(PYTHON) -m pipeline.visuals keyframes

shots: keyframes
	$(PYTHON) -m pipeline.visuals shots

music: validate
	$(PYTHON) -m pipeline.music

assemble: narration shots music
	$(PYTHON) -m pipeline.assemble

film: assemble

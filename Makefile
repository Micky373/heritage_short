PYTHON ?= $(if $(wildcard .venv/bin/python),.venv/bin/python,python3)

.PHONY: validate smoke narration radio-cut keyframes shots music assemble film

validate:
	$(PYTHON) -m pipeline.utils validate

smoke:
	$(PYTHON) -m pipeline.smoke_test

narration:
	$(PYTHON) -m pipeline.utils validate
	@echo "narration stage is validated; its processor is not implemented yet."

radio-cut:
	$(PYTHON) -m pipeline.utils validate
	@echo "radio-cut stage is validated; its processor is not implemented yet."

keyframes:
	$(PYTHON) -m pipeline.utils validate
	@echo "keyframes stage is validated; its processor is not implemented yet."

shots:
	$(PYTHON) -m pipeline.utils validate
	@echo "shots stage is validated; its processor is not implemented yet."

music:
	$(PYTHON) -m pipeline.utils validate
	@echo "music stage is validated; its processor is not implemented yet."

assemble:
	$(PYTHON) -m pipeline.utils validate
	@echo "assemble stage is validated; its processor is not implemented yet."

film: narration radio-cut keyframes shots music assemble
	$(PYTHON) -m pipeline.utils validate
	@echo "Film pipeline stages are validated; stage processors are not implemented yet."

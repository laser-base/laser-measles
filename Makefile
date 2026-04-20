.PHONY: help docs-build docs-executed-nbs docs-jenner clean-docs

PYTHON     ?= python3.12
SITE_DIR   ?= dist/mkdocs
NBS_SRC    := docs/tutorials
EXEC_DIR   ?= dist/executed_nbs
COMBINED   ?= dist/combined_mkdocs.md

help:
	@echo "laser-measles documentation targets"
	@echo "====================================="
	@echo ""
	@echo "  make docs-build         Build MkDocs HTML site -> $(SITE_DIR)/"
	@echo "  make docs-executed-nbs  Convert + execute tutorial notebooks -> $(EXEC_DIR)/"
	@echo "  make docs-jenner        Full pipeline: build + execute + concat -> $(COMBINED)"
	@echo "  make clean-docs         Remove dist/mkdocs/, dist/executed_nbs/, dist/combined_mkdocs.md"
	@echo ""
	@echo "Outputs:"
	@echo "  $(SITE_DIR)/           MkDocs HTML site"
	@echo "  $(EXEC_DIR)/           Executed tutorial notebooks (.ipynb with outputs)"
	@echo "  $(COMBINED)            Combined markdown for RAG ingest (hand to laser-mcp)"

# ── MkDocs HTML build ──────────────────────────────────────────────────────────
docs-build:
	@echo "Building MkDocs site -> $(SITE_DIR)/ ..."
	mkdocs build --site-dir $(SITE_DIR)
	@echo "Done: $(SITE_DIR)/"

# ── Notebook execution ─────────────────────────────────────────────────────────
docs-executed-nbs:
	@echo "Converting tutorial .py files to notebooks (jupytext)..."
	cd $(NBS_SRC) && $(PYTHON) convert_tutorials.py
	@echo "Executing notebooks -> $(EXEC_DIR)/ ..."
	mkdir -p $(EXEC_DIR)
	$(PYTHON) -m jupyter nbconvert \
		--to notebook \
		--execute \
		--allow-errors \
		--ExecutePreprocessor.timeout=300 \
		--output-dir $(EXEC_DIR) \
		$(NBS_SRC)/tut_*.ipynb
	@echo "Done: $(EXEC_DIR)/"

# ── Full combined markdown pipeline ───────────────────────────────────────────
docs-jenner: docs-executed-nbs docs-build
	@echo "Generating combined markdown -> $(COMBINED) ..."
	$(PYTHON) docs/concat_mkdocs.py $(SITE_DIR) $(EXEC_DIR) $(COMBINED)
	@echo ""
	@echo "RAG artifact ready: $(COMBINED)"
	@echo "Hand this file to laser-mcp: make ingest-measles COMBINED_MD=<path>"

# ── Clean ──────────────────────────────────────────────────────────────────────
clean-docs:
	rm -rf $(SITE_DIR) $(EXEC_DIR) $(COMBINED)
	@echo "Removed $(SITE_DIR)/, $(EXEC_DIR)/, $(COMBINED)"

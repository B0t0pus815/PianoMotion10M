# Makefile for thesis build artifacts.
# Requires: pandoc on PATH. For slides: marp-cli (npm i -g @marp-team/marp-cli).

THESIS_DIR := thesis
BUILD_DIR := build
CHAPTERS := \
	$(THESIS_DIR)/ch1_introduction.md \
	$(THESIS_DIR)/ch2_related_work.md \
	$(THESIS_DIR)/ch3_system_architecture.md \
	$(THESIS_DIR)/ch4_evaluation.md \
	$(THESIS_DIR)/ch5_implementation.md \
	$(THESIS_DIR)/ch6_user_experience.md \
	$(THESIS_DIR)/ch7_conclusion.md
BIB := $(THESIS_DIR)/references.bib

PANDOC := pandoc
PANDOC_FLAGS := --bibliography=$(BIB) --citeproc --toc --toc-depth=2
PDF_ENGINE := xelatex

.PHONY: all thesis slides docx tex chapter clean help

all: thesis slides

help:
	@echo "Targets:"
	@echo "  make thesis        Build $(BUILD_DIR)/thesis_full.pdf (all 7 chapters)"
	@echo "  make docx          Build $(BUILD_DIR)/thesis_full.docx (Word version)"
	@echo "  make tex           Build $(BUILD_DIR)/thesis_full.tex (LaTeX source)"
	@echo "  make slides        Build $(BUILD_DIR)/defense_slides.pdf (Marp)"
	@echo "  make chapter CH=N  Build $(BUILD_DIR)/chN.pdf (single chapter)"
	@echo "  make clean         Remove $(BUILD_DIR)/"
	@echo
	@echo "Requires pandoc on PATH; xelatex (TeX Live) for PDF;"
	@echo "marp-cli (npm i -g @marp-team/marp-cli) for slides."

$(BUILD_DIR):
	mkdir -p $@

thesis: $(BUILD_DIR)/thesis_full.pdf

$(BUILD_DIR)/thesis_full.pdf: $(CHAPTERS) $(BIB) | $(BUILD_DIR)
	$(PANDOC) $(CHAPTERS) $(PANDOC_FLAGS) \
		--pdf-engine=$(PDF_ENGINE) \
		-V CJKmainfont="Noto Sans CJK TC" \
		-V geometry=margin=1in \
		-o $@
	@echo "✓ Built $@"

docx: $(BUILD_DIR)/thesis_full.docx

$(BUILD_DIR)/thesis_full.docx: $(CHAPTERS) $(BIB) | $(BUILD_DIR)
	$(PANDOC) $(CHAPTERS) $(PANDOC_FLAGS) -o $@
	@echo "✓ Built $@"

tex: $(BUILD_DIR)/thesis_full.tex

$(BUILD_DIR)/thesis_full.tex: $(CHAPTERS) $(BIB) | $(BUILD_DIR)
	$(PANDOC) $(CHAPTERS) $(PANDOC_FLAGS) -t latex -o $@
	@echo "✓ Built $@"

# Single chapter: make chapter CH=4
chapter: | $(BUILD_DIR)
ifndef CH
	$(error CH not set. Usage: make chapter CH=4)
endif
	@CH_FILE=$$(ls $(THESIS_DIR)/ch$(CH)_*.md 2>/dev/null | head -1); \
	if [ -z "$$CH_FILE" ]; then \
		echo "ERROR: ch$(CH)_*.md not found in $(THESIS_DIR)/"; exit 1; \
	fi; \
	$(PANDOC) "$$CH_FILE" $(PANDOC_FLAGS) \
		--pdf-engine=$(PDF_ENGINE) \
		-V CJKmainfont="Noto Sans CJK TC" \
		-V geometry=margin=1in \
		-o $(BUILD_DIR)/ch$(CH).pdf
	@echo "✓ Built $(BUILD_DIR)/ch$(CH).pdf"

slides: $(BUILD_DIR)/defense_slides.pdf

$(BUILD_DIR)/defense_slides.pdf: $(THESIS_DIR)/defense_slides.md | $(BUILD_DIR)
	marp $< -o $@ --allow-local-files
	@echo "✓ Built $@"

slides-pptx: $(BUILD_DIR)/defense_slides.pptx

$(BUILD_DIR)/defense_slides.pptx: $(THESIS_DIR)/defense_slides.md | $(BUILD_DIR)
	marp $< -o $@ --allow-local-files
	@echo "✓ Built $@"

slides-html: $(BUILD_DIR)/defense_slides.html

$(BUILD_DIR)/defense_slides.html: $(THESIS_DIR)/defense_slides.md | $(BUILD_DIR)
	marp $< -o $@ --allow-local-files
	@echo "✓ Built $@"

clean:
	rm -rf $(BUILD_DIR)

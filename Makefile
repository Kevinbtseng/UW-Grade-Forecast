PDF_REPO := https://github.com/Madgrades/madgrades-pdf-archive
PDF_CACHE := data/madgrades-pdf-archive

.PHONY: pdfs parse test

pdfs:
	mkdir -p data/pdfs
	if [ -d $(PDF_CACHE)/.git ]; then git -C $(PDF_CACHE) pull --ff-only; \
	else git clone --depth 1 $(PDF_REPO) $(PDF_CACHE); fi
	cp $(PDF_CACHE)/grades/*-grades.pdf data/pdfs/

parse:
	python parser/run_parse.py

test:
	pytest

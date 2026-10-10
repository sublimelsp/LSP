# Minimal makefile for Zensical documentation

ZENSICAL = uv run --no-project --python ">=3.10" --with-requirements requirements.txt zensical

.PHONY: install build serve clean

install:
	$(ZENSICAL) --version

build:
	$(ZENSICAL) build --clean

serve:
	$(ZENSICAL) serve

clean:
	rm -rf site

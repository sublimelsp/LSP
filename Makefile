# Minimal makefile for Sphinx documentation

# You can set these variables from the command line.
SOURCEDIR     = api
BUILDDIR      = dist

.PHONY: clean

install:
	pip3 install sphinx sphinx-rtd-theme sphinx-autodoc-typehints ghp-import mkdocs mkdocs-material mkdocs-redirects
# 	sed -i -E 's/sublime\.DRAW_[A-Z_]*/0/g' source/modules/LSP/plugin/core/views.py
# 	sed -i -E 's/sublime\.HIDE_ON_MINIMAP/0/g' source/modules/LSP/plugin/core/views.py

build:
	sphinx-build -M html "$(SOURCEDIR)" "$(BUILDDIR)"

deploy:
	ghp-import --no-jekyll --push --force html

clean:
	rm -rf doctrees html

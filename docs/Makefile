# Minimal makefile for Sphinx documentation

.PHONY: clean

install:
	pip3 install mkdocs mkdocs-material mkdocs-redirects

build:
	mkdocs build

deploy:
	mkdocs gh-deploy --force

clean:
	rm -rf site

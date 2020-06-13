build_release:
	python3 ./release.py build

release:
	build_release
	python3 ./release.py publish --token `cat $HOME/.github_access_token`

build_docs:
	mkdocs

publish_docs:
	mkdocs gh-deploy

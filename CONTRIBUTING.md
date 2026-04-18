# Contributor Guidelines

## Before you start

LSP is a universal language server package.
It is not the place for language-specific logic, features or workarounds.

Sublime Text is not an IDE.
Sublime Text users may appreciate IDE-like features, but a significant number of users will want to turn these features off due to performance or to keep the package "out of the way".

Please feel free to create an issue before coding:

* If you are unsure if your proposal is suitable
* If you are unsure your solution will be technically sound

The issues also allow you to gather some feedback and help from other contributors.

## Coding

Sublime Text bundles Python 3.8, please be sure to set up your environment to match.
LSP uses [Pyright](https://microsoft.github.io/pyright) and [Ruff](https://docs.astral.sh/ruff/) to provide some code quality assurances.
Run `tox` to check your work.
Consider using [LSP-pyright](https://packages.sublimetext.io/packages/LSP-pyright) and/or [LSP-ruff](https://packages.sublimetext.io/packages/LSP-ruff) as a language server.
Enable `"pyright.dev_environment": "sublime_text_38"` in `LSP-pyright` settings to ensure that types for Sublime Text modules are known.
Changes in the code only apply after restarting Sublime Text.

## Pre-commit hooks

The repository ships a [pre-commit](https://pre-commit.com) configuration that runs linting and type-checking before every commit, matching the checks that run in CI via `tox`.

The hook delegates to `tox`, which manages the exact tool versions itself. pre-commit installs `tox` into its own isolated environment, so the checks work regardless of your shell environment or Git client.

**One-time setup:**

```sh
# Install pre-commit (uv, pipx, or pip)
uv tool install pre-commit

# Install the git hook
pre-commit install
```

To run the checks manually:

```sh
pre-commit run --all-files
```

## Testing

Please consider testing your work with other language servers, even if you do not use them.
There is also a test suite in `tests/`.
To run the tests, use the [UnitTesting](https://packages.sublimetext.io/packages/UnitTesting) package.
The configuration file for the tests is in `unittesting.json`.

## Submitting

Before you submit your pull request, please review the following:

* Any unrelated changes in there?
* Is it a bug fix? Please link the issue or attach repro, logs, screenshots etc.
* Is it a feature? Please attach screenshots / GIFs for visual changes.

We will try to help you get the PR in a mergeable shape within a reasonable time, but it may take a few days.
It is best if you check your GitHub notifications in the meantime!

## Releasing a new version (for maintainers)

* Get a log of commits since the previously released tag with `git log --format="- %s (%an)" <previous_tag>..main`
* Filter out non-relevant and non-important commits (it's not relevant to report fixes for bugs that weren't released yet, for example)
* Optionally group changes into Fixes/Features/etc.
* Create a new file in `messages/` with a file name of the yet-to-be-released version and include the changes.
* Run `./scripts/release.py build` which will bump the version and create a new commit with a new messages file included.
* If something doesn't look right in the newly created commit, delete the newly created tag manually and git reset to the previous commit making sure that you don't lose the newly created messages file.
* Run `GITHUB_TOKEN=<your_token> ./scripts/release.py publish` to push and create a new Github release.

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

LSP uses [basedpyright](https://docs.basedpyright.com) for type-checking and [Ruff](https://docs.astral.sh/ruff/) for linting and import sorting.
Run `tox` to check your work before submitting — this runs the same checks that CI enforces.

> [!NOTE]
> Changes in the plugin code only apply after restarting Sublime Text.

### Recommended editor setup

For the best in-editor experience, install [LSP-pyright](https://packages.sublimetext.io/packages/LSP-pyright) and
[LSP-ruff](https://packages.sublimetext.io/packages/LSP-ruff) packages.

**LSP-pyright** - enable the following setting to ensure that `sublime` and `sublime_plugin` module types are resolved
correctly. Add this to your `LSP-pyright` settings or to your project-specific settings:

```json
"settings": {
    "pyright.dev_environment": "sublime_text_38"
}
```

**LSP-ruff** - enable auto-fix on save so that linting violations and import ordering are corrected automatically.
Add this to your `LSP` settings or to your project-specific settings:

```json
"lsp_code_actions_on_save": {
    "source.fixAll.ruff": true,
    "source.organizeImports.ruff": true,
}
```

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

### Running the tests in Docker

You can also run the tests headlessly in a Docker container, without a local Sublime Text installation.
You must have [Docker](https://docs.docker.com/get-docker/) and a clone of the
[UnitTesting](https://github.com/SublimeText/UnitTesting) repository.
From the root of the LSP repository, run:

```sh
/path/to/UnitTesting/docker/ut-run-tests .
```

On Windows, use `ut-run-tests.cmd`.
The first run builds the Docker image and installs Sublime Text in a Docker volume.
Later runs use that volume and are faster.
The tests run on Linux, so the tests that need Windows are skipped.

Useful options:

* `--file tests/test_views.py` - run only the tests in one file. You cannot use this option together with the `--no-*`
  options.
* `--pattern "test_url*.py"` - run only the test files that match a pattern.
* `--failfast` - stop at the first failure.
* `--no-syntax-tests --no-syntax-compatibility-checks` - run only the Python unit tests.

You cannot select a single test class or method.
For all options, see the [README of the Docker runner](https://github.com/SublimeText/UnitTesting/tree/master/docker).

## Submitting

Before you submit your pull request, please review the following:

* Any unrelated changes in there?
* Is it a bug fix? Please link the issue or attach repro, logs, screenshots etc.
* Is it a feature? Please attach screenshots / GIFs for visual changes.

We will try to help you get the PR in a mergeable shape within a reasonable time, but it may take a few days.
It is best if you check your GitHub notifications in the meantime!

## Releasing a new version (for maintainers)

Releases are created by GitHub workflows:

* Run the [Prepare Release](https://github.com/sublimelsp/LSP/actions/workflows/prepare-release.yml) workflow with a version bump (`major`, `minor` or `patch`) or an exact `x.y.z` version.
  It bumps the version files, drafts `messages/<version>.txt` from the commits since the previous release and opens a `Cut <version>` pull request.
* Curate the release message in the pull request.
  Remove non-relevant and non-important changes (it's not relevant to report fixes for bugs that weren't released yet, for example) and move or remove the entries in the "Other" section.
* Merge the pull request.
  The [Release](https://github.com/sublimelsp/LSP/actions/workflows/release.yml) workflow then tags the merge commit, publishes a GitHub release with the release message and notifies `lsp_utils`.
* To abort, close the pull request and delete its branch.

The draft can also be created locally with `./scripts/release.py prepare <bump|version>`.

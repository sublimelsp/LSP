# Agent guide

## Project scope

This repository is a universal Language Server Protocol client for Sublime Text. The main language is Python.

## Repository map

- `boot.py`: package entry point, command/listener exports, and plugin lifecycle. Check registration here when adding commands or listeners.
- `plugin/`: editor-facing LSP features such as completion, hover, diagnostics, formatting, and document synchronization.
- `plugin/core/`: shared sessions, JSON-RPC, transports, configuration, workspace handling, UI helpers, and protocol request/response utilities.
- `plugin/api.py`: public extension API used by language-server packages. Treat changes to its contracts as compatibility-sensitive.
- `protocol/__init__.py`: generated LSP types. It is marked `DO NOT EDIT`; locate the generation workflow before changing generated definitions.
- `stubs/`: type stubs used by static analysis.
- `tests/`: Sublime Text UnitTesting suite, shared fixtures in `tests/setup.py`, and a fake language server in `tests/server.py`.
- `LSP.sublime-settings` and `LanguageServers.sublime-settings`: package and server settings. Commands, key bindings, menus, syntaxes, and CSS live in the corresponding Sublime resource files.
- `docs/src/`: documentation sources; `docs/mkdocs.yml`: site configuration.
- `third_party/`: vendored code. Keep unrelated cleanup out of this directory.
- `messages/`, `messages.json`, `VERSION`, and `scripts/release.py`: release metadata and tooling; update these as part of an explicit release task.

## Making code changes

- Read `CONTRIBUTING.md` before making changes.
- Use `pyproject.toml` as the source of truth for linting and type-checking configuration.
- Use the `format` skill to understand how to format your changes.
- Use the `lint` skill to understand how to run linters and type checkers.
- If skill loading is unavailable, read .agents/skills/format/skill.md and .agents/skills/lint/skill.md directly.
- Use ASCII for newly written code, prose and comments. Preserve existing Unicode, and allow Unicode literals where required for functionality or test coverage.
- Use full English sentences when writing prose in docstrings.
- When fixing a bug, make minimal changes.
- Plugin code targets Sublime Text's Python 3.8 runtime, even when development tools run under a newer Python. Avoid newer runtime APIs and syntax that cannot run on Python 3.8.
- Preserve compatibility with supported Sublime Text builds; check existing version guards before using newer editor APIs.
- Reuse existing session, request, promise, URI, and position-conversion helpers rather than introducing parallel abstractions.
- When changing user-facing behavior, update relevant settings, command/menu resources, and documentation together.

## Transparent communication & disclosure

- When tasked with writing a git commit message: at the bottom of the message, add the line "Assisted-By: HARNESS:MODEL", where HARNESS is the harness you are in (e.g. VSCode, OpenCode, Codex CLI, Cursor), and MODEL is your large language model identifier (e.g. claude-sonnet-5, claude-opus-5, gpt-6-astra).
- When tasked with opening an issue, or commenting on an issue, or replying to an issue: apply the same rule as for git commit messages.

## Documentation

For documentation changes, use Zensical from `docs/`: `zensical serve` for a preview or `zensical build --clean` to build the site. Edit `docs/src/`, not the generated `docs/site/` output.

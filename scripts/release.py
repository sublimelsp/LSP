#!/usr/bin/env python3
"""
Release tooling, used by the "Prepare Release" and "Release" GitHub workflows.

- `prepare <bump|version>` bumps the version files and drafts `messages/<version>.txt` from the commit log.
- `tag` prints the git tag name for the current version.
- `notes` prints the GitHub release notes for the current version.
"""
from __future__ import annotations

from pathlib import Path
from typing import Generator
import argparse
import json
import re
import subprocess
import sys

PACKAGE_PATH = Path(__file__).resolve().parent.parent
MESSAGE_DIR = 'messages'
MESSAGE_PATH = PACKAGE_PATH / MESSAGE_DIR
VERSION_PATH = PACKAGE_PATH / 'VERSION'
CONFIGURATION = json.loads((PACKAGE_PATH / '.release.json').read_text(encoding='utf-8'))

# The prefix to use for release version number. For example with prefix "4000" the version will be "4000-x.y.z".
RELEASE_VERSION_PREFIX = CONFIGURATION['publish_version_prefix'] or ''
PYTHON_VERSION_PATH = CONFIGURATION.get('python_version_path', None)

# Maps conventional commit types to the sections of the drafted release message, in order of appearance.
# Commits of other types (chore, ci, build, test, ...) are left out of the draft.
SECTIONS = {
    'feat': 'Features',
    'fix': 'Fixes',
    'perf': 'Performance',
    'refactor': 'Refactors',
    'docs': 'Documentation',
}
# Section for commits without a conventional commit type.
OTHER_SECTION = 'Other'
COMMIT_PATTERN = re.compile(r'^(?P<type>[a-z]+)(?:\([^)]*\))?!?:\s*(?P<description>.+)$')
VERSION_PATTERN = re.compile(r'^\d+\.\d+\.\d+$')
BUMPS = ('major', 'minor', 'patch')


def build_messages_json(version_history: list[str]) -> None:
    """Write the version history to the messages.json file."""
    with (PACKAGE_PATH / 'messages.json').open('w', encoding='utf-8') as file:
        json.dump(
            obj={v: MESSAGE_DIR + '/' + v + '.txt' for v in version_history},
            fp=file, indent=4, separators=(',', ': '), sort_keys=True)
        file.write('\n')


def version_history() -> list[str]:
    """Return a list of all releases."""
    def generator() -> Generator[str, None, None]:
        for path in MESSAGE_PATH.iterdir():
            if path.suffix.lower() == '.txt':
                yield path.stem

    return sorted(generator(), key=parse_version)


def parse_version(version: str) -> tuple[int, int, int]:
    """Convert filename to version tuple (major, minor, patch)."""
    match = re.match(
        r'(?:(?P<prefix>[^.-]+)\-)?(?P<major>\d+)\.(?P<minor>\d+)\.(?P<patch>\d+)(?:-.+)?', version)
    if match:
        _prefix, major, minor, patch = match.groups()
        return int(major), int(minor), int(patch)
    return 0, 0, 0


def get_version_with_prefix(version: str) -> str:
    if RELEASE_VERSION_PREFIX:
        return f'{RELEASE_VERSION_PREFIX}-{version}'
    return version


def current_version() -> str:
    return VERSION_PATH.read_text(encoding='utf-8').strip()


def next_version(current: str, target: str) -> str:
    """Return the version for `target`, which is either a bump type or an exact version."""
    if VERSION_PATTERN.match(target):
        return target
    if target not in BUMPS:
        fail(f'Invalid version "{target}". Expected one of {", ".join(BUMPS)} or an x.y.z version.')
    major, minor, patch = parse_version(current)
    if target == 'major':
        return f'{major + 1}.0.0'
    if target == 'minor':
        return f'{major}.{minor + 1}.0'
    return f'{major}.{minor}.{patch + 1}'


def git(*args: str) -> str:
    """Run git command within current package path."""
    return subprocess.run(
        ['git', *args],  # ruff: ignore[start-process-with-partial-path]
        cwd=PACKAGE_PATH, check=True, capture_output=True, encoding='utf-8').stdout.strip()


def draft_message(version: str, previous_tag: str) -> str:
    """Draft the release message from the commits since `previous_tag`, grouped by conventional commit type."""
    sections: dict[str, list[str]] = {title: [] for title in [*SECTIONS.values(), OTHER_SECTION]}
    log = git('log', '--format=%s%x1f%an', f'{previous_tag}..HEAD')
    for line in log.splitlines():
        subject, author = line.split('\x1f', 1)
        if subject.startswith('Cut '):
            continue
        match = COMMIT_PATTERN.match(subject)
        if match:
            title = SECTIONS.get(match.group('type'))
            if not title:
                continue
            description = match.group('description')
        else:
            title = OTHER_SECTION
            description = subject
        sections[title].append(f'- {description[:1].upper()}{description[1:]} ({author})')
    parts = [f'=> {version}']
    for title, entries in sections.items():
        if entries:
            parts.extend((f'# {title}', '\n'.join(entries)))
    return '\n\n'.join(parts) + '\n'


def prepare_release(args: argparse.Namespace) -> None:
    """Bump the version files and draft the release message for the new version."""
    current = current_version()
    version = next_version(current, args.version)
    if parse_version(version) <= parse_version(current):
        fail(f'New version {version} must be greater than the current version {current}.')
    message_path = MESSAGE_PATH / f'{version}.txt'
    if not message_path.exists():
        message_path.write_text(draft_message(version, get_version_with_prefix(current)), encoding='utf-8')
    VERSION_PATH.write_text(version, encoding='utf-8')
    if PYTHON_VERSION_PATH:
        (PACKAGE_PATH / PYTHON_VERSION_PATH).write_text(
            f'from __future__ import annotations\n\n__version__ = {parse_version(version)}\n', encoding='utf-8')
    build_messages_json(version_history())
    print(version)


def print_tag(_: argparse.Namespace) -> None:
    """Print the git tag name of the current version."""
    print(get_version_with_prefix(current_version()))


def print_notes(_: argparse.Namespace) -> None:
    """Print the GitHub release notes of the current version."""
    version = current_version()
    message_path = MESSAGE_PATH / f'{version}.txt'
    if not message_path.exists():
        fail(f'Release message {message_path.relative_to(PACKAGE_PATH)} does not exist.')
    text = message_path.read_text(encoding='utf-8')
    # strip message header (version)
    print(text[text.find('\n') + 1:].strip())


def fail(message: str) -> None:
    print(message, file=sys.stderr)
    sys.exit(1)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Prepares LSP releases')
    subparsers = parser.add_subparsers(help='Available commands')
    prepare_parser = subparsers.add_parser('prepare', help='Bump the version and draft the release message')
    prepare_parser.add_argument('version', help=f'One of {", ".join(BUMPS)} or an exact x.y.z version')
    prepare_parser.set_defaults(func=prepare_release)
    tag_parser = subparsers.add_parser('tag', help='Print the git tag of the current version')
    tag_parser.set_defaults(func=print_tag)
    notes_parser = subparsers.add_parser('notes', help='Print the release notes of the current version')
    notes_parser.set_defaults(func=print_notes)
    args = parser.parse_args()
    if 'func' not in args:
        parser.print_help()
    else:
        args.func(args)

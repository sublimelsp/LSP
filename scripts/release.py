#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from typing import Generator, List, Optional, Tuple
import argparse
import json
import os
import re
import subprocess
import sys

# Internal
PACKAGE_PATH = os.path.realpath(os.path.join(os.path.join(os.path.dirname(__file__), '..')))
MESSAGE_DIR = 'messages'
MESSAGE_PATH = os.path.join(PACKAGE_PATH, MESSAGE_DIR)

with open(os.path.join(PACKAGE_PATH, '.release.json'), 'r') as f:
    CONFIGURATION = json.load(f)

# Project configuration
# The name of the branch to push to the remote on releasing.
RELEASE_BRANCH = CONFIGURATION['push_branch']
# The name of the GitHub repository in <owner>/<repo> format
GITHUB_REPO = CONFIGURATION['publish_repo']
# The prefix to use for release version number. For example with prefix "4000" the version will be "4000-x.y.z".
RELEASE_VERSION_PREFIX = CONFIGURATION['publish_version_prefix'] or ''
# The name of the settings file to get the release token from ("github_token" setting)
SETTINGS = '{}.sublime-settings'.format(__package__)
PYTHON_VERSION_PATH = CONFIGURATION.get('python_version_path', None)


def get_message(fname: str) -> str:
    with open(fname, 'r', encoding='utf-8') as file:
        message = file.read()
    return message


def put_message(fname: str, text: str) -> None:
    with open(fname, 'w', encoding='utf-8') as file:
        file.write(text)


def build_messages_json(version_history: List[str]) -> None:
    """Write the version history to the messages.json file."""
    output = os.path.join(PACKAGE_PATH, 'messages.json')
    with open(output, 'w+', encoding='utf-8') as file:
        json.dump(
            obj={v: MESSAGE_DIR + '/' + v + '.txt' for v in version_history},
            fp=file, indent=4, separators=(',', ': '), sort_keys=True)
        file.write('\n')


def version_history() -> List[str]:
    """Return a list of all releases."""
    def generator() -> Generator[str, None, None]:
        for filename in os.listdir(MESSAGE_PATH):
            basename, ext = os.path.splitext(filename)
            if ext.lower() == '.txt':
                yield basename

    return sorted(tuple(generator()), key=parse_version)


def parse_version(version: str) -> Tuple[int, int, int]:
    """Convert filename to version tuple (major, minor, patch)."""
    match = re.match(
        r'(?:(?P<prefix>[^.-]+)\-)?(?P<major>\d+)\.(?P<minor>\d+)\.(?P<patch>\d+)(?:-.+)?', version)
    if match:
        prefix, major, minor, patch = match.groups()
        return int(major), int(minor), int(patch)
    else:
        return 0, 0, 0

def get_version_with_prefix(version: str) -> str:
    if RELEASE_VERSION_PREFIX:
        return '{}-{}'.format(RELEASE_VERSION_PREFIX, version)
    return version


def git(*args: str) -> Optional[str]:
    """Run git command within current package path."""
    if os.name == 'nt':
        startupinfo = subprocess.STARTUPINFO()  # type: ignore
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW  # type: ignore
    else:
        startupinfo = None
    proc = subprocess.Popen(
        args=['git'] + [arg for arg in args], startupinfo=startupinfo,
        stdout=subprocess.PIPE, stdin=subprocess.PIPE, cwd=PACKAGE_PATH)
    stdout, _ = proc.communicate()
    return stdout.decode('utf-8').strip() if stdout else None


def commit_release(version: str) -> None:
    """Create a 'Cut <version>' commit and tag."""
    commit_message = 'Cut %s' % version
    git('add', '.')
    git('commit', '-m', commit_message)
    git('tag', '-a', '-m', commit_message, get_version_with_prefix(version))


def build_release(args: argparse.Namespace) -> None:
    """Build the new release locally."""
    history = version_history()
    version = history[-1]
    put_message(os.path.join(PACKAGE_PATH, 'VERSION'), version)
    if PYTHON_VERSION_PATH:
        version_tuple = parse_version(version)
        put_message(PYTHON_VERSION_PATH, '__version__ = {}\n'.format(version_tuple))
    build_messages_json(history)
    commit_release(version)
    print("Release %s created!" % version)


def publish_release(args: argparse.Namespace) -> None:
    """Publish the new release."""
    if not args.token:
        print('The GitHub token must be provided either through argument or GITHUB_TOKEN environment variable.')
        sys.exit(1)

    version = get_message(os.path.join(PACKAGE_PATH, 'VERSION'))
    version_with_prefix = get_version_with_prefix(version)

    repo_url = 'git@github.com:{}'.format(GITHUB_REPO)
    # push release branch to server
    git('push', repo_url, RELEASE_BRANCH)
    # push tags to server
    git('push', repo_url, 'tag', version_with_prefix)

    # publish the release
    post_url = '/repos/{}/releases'.format(GITHUB_REPO)
    headers = {
        'Authorization': 'token {}'.format(args.token),
        'User-Agent': 'Sublime Text',
        'Content-type': 'application/json',
    }
    # get message from /messages/<version>.txt
    text = get_message(os.path.join(MESSAGE_PATH, version + '.txt'))
    # strip message header (version)
    text = text[text.find('\n') + 1:].strip()
    # built the JSON request body
    data = json.dumps({
        "tag_name": version_with_prefix,
        "target_commitish": RELEASE_BRANCH,
        "name": version_with_prefix,
        "body": text,
        "draft": False,
        "prerelease": False
    })
    try:
        import http.client
        client = http.client.HTTPSConnection('api.github.com')
        client.request('POST', post_url, body=data, headers=headers)
        response = client.getresponse()
        print("Release %s published!" % version_with_prefix
              if response.status == 201 else
              "Release %s failed!" % version_with_prefix)
    finally:
        client.close()


"""
======================================
Command Line Interface
======================================
"""
if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description='Buils and Publishes {} Releases'.format(__package__))
    subparsers = parser.add_subparsers(help='Available commands')
    build_parser = subparsers.add_parser('build', help='Build a release')
    build_parser.set_defaults(func=build_release)
    publish_parser = subparsers.add_parser('publish', help='Publish a release')
    publish_parser.add_argument(
        '--token',
        nargs='?',
        default=os.environ.get('GITHUB_TOKEN', None),
        help='The GitHub access token used for authentication.')
    publish_parser.set_defaults(func=publish_release)
    args = parser.parse_args()
    if 'func' not in args:
        parser.print_help()
    else:
        args.func(args)

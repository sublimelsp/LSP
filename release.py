#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from typing import Generator, List, Optional, Tuple
import json
import os
import re
import subprocess

# Internal
PACKAGE_PATH = os.path.dirname(__file__)
MESSAGE_DIR = 'messages'
MESSAGE_PATH = os.path.join(PACKAGE_PATH, MESSAGE_DIR)

with open(os.path.join(PACKAGE_PATH, '.release.json'), 'r') as f:
    CONFIGURATION = json.load(f)

# Project configuration
# The name of the branch to push to the remote on releasing.
RELEASE_BRANCH = CONFIGURATION['push_branch']
# The name of the GitHub repository in <owner>/<repo> format
GITHUB_REPO = CONFIGURATION['publish_repo']
# The name of the settings file to get the release token from ("github_token" setting)
SETTINGS = '{}.sublime-settings'.format(__package__)
VERSION_FILE_PATH = CONFIGURATION['version_file_path']


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
    git('tag', '-a', '-m', commit_message, version)


def build_release() -> None:
    """Build the new release locally."""
    history = version_history()
    version = history[-1]
    version_tuple = parse_version(version)
    put_message(VERSION_FILE_PATH, '__version__ = {}\n'.format(version_tuple))
    build_messages_json(history)
    commit_release(version)
    print("Release %s created!" % version)


def publish_release(token: str) -> None:
    """Publish the new release."""
    version = get_message(VERSION_FILE_PATH)

    repo_url = 'https://github.com/{}'.format(GITHUB_REPO)
    # push release branch to server
    git('push', repo_url, RELEASE_BRANCH)
    # push tags to server
    git('push', repo_url, 'tag', version)

    # publish the release
    post_url = '/repos/{}/releases?access_token={}'.format(GITHUB_REPO, token)
    headers = {
        'User-Agent': 'Sublime Text',
        'Content-type': 'application/json',
    }
    # get message from /messages/<version>.txt
    text = get_message(os.path.join(MESSAGE_PATH, version + '.txt'))
    # strip message header (version)
    text = text[text.find('\n') + 1:]
    # built the JSON request body
    data = json.dumps({
        "tag_name": version,
        "target_commitish": RELEASE_BRANCH,
        "name": version,
        "body": text,
        "draft": False,
        "prerelease": False
    })
    try:
        import http.client
        client = http.client.HTTPSConnection('api.github.com')
        client.request('POST', post_url, body=data, headers=headers)
        response = client.getresponse()
        print("Release %s published!" % version
              if response.status == 201 else
              "Release %s failed!" % version)
    finally:
        client.close()


"""
======================================
Command Line Interface
======================================
"""
if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(
        description='Built and Publish {} Releases'.format(__package__))
    parser.add_argument(
        dest='command',
        help='The command to perform is one of [BUILD|PUBLISH].')
    parser.add_argument(
        '--token',
        nargs='?',
        default=os.environ.get('GITHUB_TOKEN', None),
        help='The GitHub access token used for authentication.')
    args = parser.parse_args()
    if args.command.lower() == 'build':
        build_release()
    elif args.command.lower() == 'publish':
        publish_release(args.token)

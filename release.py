# -*- coding: utf-8 -*-
#!/usr/bin/python

import json
import os
import re
import subprocess

try:
    from typing import Generator, List, Optional, Tuple
except ImportError:
    from LSP.plugin.core.typing import Generator, List, Optional, Tuple

# Project configuration
# The name of the branch to push to the remote on releasing.
RELEASE_BRANCH = 'st4000-exploration'
# The name of the GitHub repository in <owner>/<repo> format
GITHUB_REPO = 'sublimelsp/LSP'
# The name of the settings file to get the release token from ("github_token" setting)
SETTINGS = '{}.sublime-settings'.format(__package__)
# The prefix to use for the <prefix>_build_release and <prefix>_publish_release commands
# that can be used in the command palette and other contexts. Can contain underscores.
COMMAND_PREFIX = 'lsp'

# Internal
PACKAGE_PATH = os.path.dirname(__file__)
MESSAGE_DIR = 'messages'
MESSAGE_PATH = os.path.join(PACKAGE_PATH, MESSAGE_DIR)


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

    def sortkey(key: str) -> Tuple[int, int, int]:
        """Convert filename to version tuple (major, minor, patch)."""
        match = re.match(
            r'(?:(?P<prefix>[^.-]+)\-)?(?P<major>\d+)\.(?P<minor>\d+)\.(?P<patch>\d+)(?:-.+)?', key)
        if match:
            prefix, major, minor, patch = match.groups()
            return int(major), int(minor), int(patch)
        else:
            return 0, 0, 0

    return sorted(tuple(generator()), key=sortkey)


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
    put_message(os.path.join(PACKAGE_PATH, 'VERSION'), version)
    build_messages_json(history)
    commit_release(version)
    print("Release %s created!" % version)


def publish_release(token: str) -> None:
    """Publish the new release."""
    version = get_message(os.path.join(PACKAGE_PATH, 'VERSION'))

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
        help='The GitHub access token used for authentication.')
    args = parser.parse_args()
    if args.command.lower() == 'build':
        build_release()
    elif args.command.lower() == 'publish':
        publish_release(args.token)


"""
======================================
Sublime Text Command Interface
======================================
"""
try:
    import sublime
    import sublime_plugin

    camel_case_prefix = ''.join([word.title() for word in COMMAND_PREFIX.lower().split('_')])

    class InternalBuildReleaseCommand(sublime_plugin.ApplicationCommand):

        def is_visible(self) -> bool:
            settings = sublime.load_settings(SETTINGS)
            return settings.has('github_token')

        def run(self) -> None:
            """Built a new release."""
            build_release()

    InternalBuildReleaseCommand.__name__ = '{}BuildReleaseCommand'.format(camel_case_prefix)

    class InternalPublishReleaseCommand(sublime_plugin.ApplicationCommand):

        def is_visible(self) -> bool:
            settings = sublime.load_settings(SETTINGS)
            return settings.has('github_token')

        def run(self) -> None:
            """Publish the new release."""
            settings = sublime.load_settings(SETTINGS)
            publish_release(settings.get('github_token') or '')

    InternalBuildReleaseCommand.__name__ = '{}PublishReleaseCommand'.format(camel_case_prefix)

except ImportError:
    pass

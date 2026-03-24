from __future__ import annotations

from ...protocol import CodeAction
from ...protocol import Command
from ...protocol import DocumentUri
from ...protocol import URI
from .constants import ST_INSTALLED_PACKAGES_PATH
from .constants import ST_PACKAGES_PATH
from base64 import urlsafe_b64decode
from base64 import urlsafe_b64encode
from typing import Any
from typing import cast
from typing_extensions import deprecated
from urllib.parse import urljoin
from urllib.parse import urlparse
from urllib.request import pathname2url
from urllib.request import url2pathname
import json
import os
import re
import sublime

CODE_ACTION_SCHEME = 'code-action'


def normalize_uri(uri: DocumentUri) -> DocumentUri:
    return unparse_uri(parse_uri(uri))


def filename_to_uri(file_name: str) -> str:
    """Convert a file name obtained from view.file_name() into an URI."""
    prefix = ST_INSTALLED_PACKAGES_PATH
    if file_name.startswith(prefix):
        return _to_resource_uri(file_name, prefix)
    prefix = ST_PACKAGES_PATH
    if file_name.startswith(prefix) and not os.path.exists(file_name):
        return _to_resource_uri(file_name, prefix)
    path = pathname2url(file_name)
    return urljoin("file:", path)


def view_to_uri(view: sublime.View) -> str:
    file_name = view.file_name()
    if not file_name:
        return f"buffer:{view.buffer_id()}"
    return filename_to_uri(file_name)


@deprecated("Use parse_uri() instead")
def uri_to_filename(uri: str) -> str:
    """
    DEPRECATED: An URI associated to a view does not necessarily have a "file:" scheme.
    Use parse_uri instead.
    """
    scheme, path = parse_uri(uri)
    assert scheme == "file"
    return path


def parse_uri(uri: str) -> tuple[str, str]:
    """
    Parses an URI into a tuple where the first element is the URI scheme. The
    second element is the local filesystem path if the URI is a file URI,
    otherwise the second element is the original URI.
    """
    parsed = urlparse(uri)
    if parsed.scheme == "file":
        path = url2pathname(parsed.path)
        if os.name == 'nt':
            netloc = url2pathname(parsed.netloc)
            path = path.lstrip("\\")
            path = re.sub(r"^/([a-zA-Z]:)", r"\1", path)  # remove slash preceding drive letter
            path = re.sub(r"^([a-z]):", _uppercase_driveletter, path)
            if netloc:
                # Convert to UNC path
                return parsed.scheme, f"\\\\{netloc}\\{path}"
            else:
                return parsed.scheme, path
        return parsed.scheme, path
    elif parsed.scheme == '' and ':' in parsed.path.split('/')[0]:
        # workaround for bug in urllib.parse.urlparse
        return parsed.path.split(':')[0], uri
    return parsed.scheme, uri


def unparse_uri(parsed_uri: tuple[str, str]) -> str:
    """Reverse of `parse_uri()`."""
    scheme, path = parsed_uri
    return filename_to_uri(path) if scheme == "file" else path


def _to_resource_uri(path: str, prefix: str) -> str:
    """
    Terrible hacks from ST core leak into packages as well.

    See: https://github.com/sublimehq/sublime_text/issues/3742
    """
    return f"res:/Packages{pathname2url(path[len(prefix):])}"


def _uppercase_driveletter(match: Any) -> str:
    """For compatibility with Sublime's VCS status in the status bar."""
    return f"{match.group(1).upper()}:"


def encode_code_action_uri(session_name: str, action: Command | CodeAction) -> URI:
    return f'{CODE_ACTION_SCHEME}:{session_name}/{urlsafe_b64encode(json.dumps(action).encode()).decode()}'


def decode_code_action_uri(uri: URI) -> tuple[str, Command | CodeAction]:
    scheme = parse_uri(uri)[0]
    if scheme != CODE_ACTION_SCHEME:
        raise ValueError(f'Unsupported URI scheme: {scheme}')
    session_name, _, data = uri[len(CODE_ACTION_SCHEME) + 1:].partition('/')
    action = cast('Command | CodeAction', json.loads(urlsafe_b64decode(data.encode()).decode()))
    return session_name, action

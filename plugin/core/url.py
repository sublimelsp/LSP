from .typing import Any, Optional
from urllib.parse import quote
from urllib.parse import urljoin
from urllib.parse import urlparse
from urllib.request import pathname2url
from urllib.request import url2pathname
import os
import re

import sublime


def filename_to_uri(file_name: str) -> str:
    """
    Convert a file name obtained from view.file_name() into an URI
    """
    prefix = sublime.installed_packages_path()
    if file_name.startswith(prefix):
        return _to_resource_uri(file_name, prefix)
    prefix = sublime.packages_path()
    if file_name.startswith(prefix) and not os.path.exists(file_name):
        return _to_resource_uri(file_name, prefix)
    path = pathname2url(file_name)
    re.sub(r"^([A-Z]):/", _lowercase_driveletter, path)
    return urljoin("file:", path)


def view_to_uri(view: sublime.View, foreign_uri: Optional[str] = None) -> str:
    if isinstance(foreign_uri, str):
        return foreign_uri
    file_name = view.file_name()
    if not file_name:
        return "buffer://sublime/{}".format(view.buffer_id())
    return filename_to_uri(file_name)


def uri_to_filename(uri: str) -> str:
    """
    DEPRECATED: An URI associated to a view does not necessarily have a "file:" scheme.
    Use urllib.parse.urlparse to determine the scheme and go from there.
    Use urllib.parse.unquote to unquote the path.
    """
    parsed = urlparse(uri)
    assert parsed.scheme == "file"
    if os.name == 'nt':
        # url2pathname does not understand %3A (VS Code's encoding forced on all servers :/)
        return url2pathname(parsed.path).strip('\\')
    else:
        return url2pathname(parsed.path)


def _to_resource_uri(path: str, prefix: str) -> str:
    """
    Terrible hacks from ST core leak into packages as well.

    See: https://github.com/sublimehq/sublime_text/issues/3742
    """
    return "res://Packages{}".format(quote(path[len(prefix):]))


def _lowercase_driveletter(match: Any) -> str:
    """
    For compatibility with certain other language clients.
    """
    return "{}:/".format(match.group(1).lower())

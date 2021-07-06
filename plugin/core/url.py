from .typing import Any, Tuple
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
    return urljoin("file:", path)


def view_to_uri(view: sublime.View) -> str:
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
        path = url2pathname(parsed.path).strip('\\')
        return re.sub(r"^([a-z]):", _uppercase_driveletter, path)
    else:
        return url2pathname(parsed.path)


def parse_uri(uri: str) -> Tuple[str, str]:
    """
    Parses an URI into a tuple where the first element is the URI scheme. The
    second element is the local filesystem path if the URI is a file URI,
    otherwise the second element is the original URI.
    """
    parsed = urlparse(uri)
    if parsed.scheme == "file":
        if os.name == 'nt':
            # TODO: this is wrong for UNC paths
            return parsed.scheme, url2pathname(parsed.path).strip('\\')
        return parsed.scheme, url2pathname(parsed.path)
    return parsed.scheme, uri


def _to_resource_uri(path: str, prefix: str) -> str:
    """
    Terrible hacks from ST core leak into packages as well.

    See: https://github.com/sublimehq/sublime_text/issues/3742
    """
    return "res://Packages{}".format(pathname2url(path[len(prefix):]))


def _uppercase_driveletter(match: Any) -> str:
    """
    For compatibility with Sublime's VCS status in the status bar.
    """
    return "{}:".format(match.group(1).upper())

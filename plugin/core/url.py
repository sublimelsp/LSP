from urllib.parse import urljoin
from urllib.parse import urlparse
from urllib.request import pathname2url
from urllib.request import url2pathname
import os


def filename_to_uri(path: str) -> str:
    return urljoin('file:', pathname2url(path))


def uri_to_filename(uri: str) -> str:
    parsed = urlparse(uri)
    assert parsed.scheme == "file"
    if os.name == 'nt':
        # url2pathname does not understand %3A (VS Code's encoding forced on all servers :/)
        return url2pathname(parsed.path).strip('\\')
    else:
        return url2pathname(parsed.path)

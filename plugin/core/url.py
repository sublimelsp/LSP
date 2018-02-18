from urllib.parse import urljoin
from urllib.parse import urlparse
from urllib.request import pathname2url
from urllib.request import url2pathname
import re


def filename_to_uri(path: str) -> str:
    return urljoin('file:', pathname2url(path))


def uri_to_filename(uri: str) -> str:
    prog = re.compile(r'\\[a-zA-Z]:\\.+')
    ret = url2pathname(urlparse(uri).path)
    if prog.match(ret):
        ret = ret[1:]
    return ret

from .types import ClientConfig
from .typing import Optional
from urllib.parse import urljoin
from urllib.parse import urlparse
from urllib.request import pathname2url
from urllib.request import url2pathname
import os


def filename_to_uri(path: str, config: Optional[ClientConfig] = None) -> str:
    if config:
        return config.map_client_path_to_server_uri(path)
    else:
        # DEPRECATED
        return urljoin('file:', pathname2url(path))


def uri_to_filename(uri: str, config: Optional[ClientConfig] = None) -> str:
    if config:
        return config.map_server_uri_to_client_path(uri)
    else:
        # DEPRECATED
        if os.name == 'nt':
            # url2pathname does not understand %3A (VS Code's encoding forced on all servers :/)
            return url2pathname(urlparse(uri).path).strip('\\')
        else:
            return url2pathname(urlparse(uri).path)

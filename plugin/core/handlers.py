import abc
from .settings import ClientConfig
from .rpc import Client
try:
    from typing import Any, List, Dict, Tuple, Callable, Optional, Set
    assert Any and List and Dict and Tuple and Callable and Optional and Set
except ImportError:
    pass


class LanguageHandler(object):
    __metaclass__ = abc.ABCMeta

    @abc.abstractproperty
    def name(self) -> str:
        pass

    @abc.abstractproperty
    def config(self) -> ClientConfig:
        pass

    def on_enable(self) -> None:
        pass

    def on_initialized(self, client: Client) -> None:
        pass


def get_language_handlers() -> 'List[LanguageHandler]':
    return list(cls() for cls in LanguageHandler.__subclasses__())

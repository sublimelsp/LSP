import abc
from .settings import ClientConfig
# from .rpc import Client
try:
    from typing import Any, List, Dict, Tuple, Callable, Optional, Set, Type
    assert Any and List and Dict and Tuple and Callable and Optional and Set
except ImportError:
    pass


class LanguageHandler(metaclass=abc.ABCMeta):
    @abc.abstractproperty
    def name(self) -> str:
        raise NotImplementedError

    @abc.abstractproperty
    def config(self) -> ClientConfig:
        raise NotImplementedError

    # def on_enable(self) -> None:
    #     pass

    # def on_initialized(self, client: Client) -> None:
    #     pass

    @classmethod
    def instantiate_all(cls) -> 'List[LanguageHandler]':
        return list(
            instantiate(c) for c in cls.__subclasses__()
            if issubclass(c, LanguageHandler))


def instantiate(c: Type[LanguageHandler]) -> LanguageHandler:
    return c()

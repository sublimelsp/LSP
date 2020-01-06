from .types import ClientConfig
from .typing import List, Callable, Optional, Type
import abc


class LanguageHandler(metaclass=abc.ABCMeta):
    on_start = None  # type: Optional[Callable]
    on_initialized = None  # type: Optional[Callable]

    @abc.abstractproperty
    def name(self) -> str:
        raise NotImplementedError

    @abc.abstractproperty
    def config(self) -> ClientConfig:
        raise NotImplementedError

    @classmethod
    def instantiate_all(cls) -> 'List[LanguageHandler]':
        return list(
            instantiate(c) for c in cls.__subclasses__()
            if issubclass(c, LanguageHandler))


def instantiate(c: Type[LanguageHandler]) -> LanguageHandler:
    return c()

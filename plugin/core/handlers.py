import abc
from .logging import exception_log
from .types import ClientConfig
try:
    from typing import List, Callable, Optional, Type
    assert List and Callable and Optional and Type
except ImportError:
    pass


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
        result = []
        for c in cls.__subclasses__():
            if issubclass(c, LanguageHandler):
                try:
                    instance = instantiate(c)
                    result.append(instance)
                except Exception as ex:
                    exception_log('Failed to instantiate language handler "{}"'.format(c.__name__), ex)
        return result


def instantiate(c: 'Type[LanguageHandler]') -> LanguageHandler:
    return c()

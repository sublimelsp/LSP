from .logging import exception_log
from .types import ClientConfig
from .typing import List, Callable, Optional
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
        result = []
        for c in cls.__subclasses__():
            if issubclass(c, LanguageHandler):
                try:
                    instance = c()
                except Exception as ex:
                    exception_log("Failed to instantiate LanguageHandler", ex)
                    continue
                result.append(instance)
        return result

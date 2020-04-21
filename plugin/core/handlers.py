from .types import ClientConfig
from .logging import exception_log
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
        result = []  # type: List[LanguageHandler]
        for c in cls.__subclasses__():
            if issubclass(c, LanguageHandler):
                try:
                    instance = c()
                    result.append(instance)
                except Exception as ex:
                    exception_log("Failed to instantiate language handler {}".format(c.__name__), ex)
        return result

from .logging import debug
from .types import ClientConfig
from .typing import Dict, List, Callable, Optional, Type
from .views import get_storage_path
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
    def additional_variables(cls) -> Optional[Dict[str, str]]:
        return None

    @classmethod
    def storage_path(cls) -> str:
        """
        The storage path. Use this as your base directory to install server files. Its path is '$DATA/Package Storage'.
        You should have an additional subdirectory preferrably the same name as your handler.
        """
        return get_storage_path()

    @classmethod
    def instantiate_all(cls) -> 'List[LanguageHandler]':
        def get_final_subclasses(derived: 'List[Type[LanguageHandler]]',
                                 results: 'List[Type[LanguageHandler]]') -> None:
            for d in derived:
                d_subclasses = d.__subclasses__()
                if len(d_subclasses) > 0:
                    get_final_subclasses(d_subclasses, results)
                else:
                    results.append(d)

        subclasses = []  # type: List[Type[LanguageHandler]]
        get_final_subclasses(cls.__subclasses__(), subclasses)
        instantiated = []
        for c in subclasses:
            try:
                instantiated.append(instantiate(c))
            except Exception as e:
                debug('LanguageHandler instantiation crashed!', e)
        return instantiated


def instantiate(c: Type[LanguageHandler]) -> LanguageHandler:
    return c()

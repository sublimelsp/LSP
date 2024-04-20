import sys
from enum import Enum, IntEnum, IntFlag  # noqa: F401
from typing import (  # noqa: F401
    IO,  # noqa: F401
    TYPE_CHECKING,  # noqa: F401
    Any,  # noqa: F401
    Callable,  # noqa: F401
    Deque,  # noqa: F401
    Dict,  # noqa: F401
    Generator,  # noqa: F401
    Generic,  # noqa: F401
    Iterable,  # noqa: F401
    Iterator,  # noqa: F401
    List,  # noqa: F401
    Literal,  # noqa: F401
    Mapping,  # noqa: F401
    Optional,  # noqa: F401
    Protocol,  # noqa: F401
    Sequence,  # noqa: F401
    Set,  # noqa: F401
    Tuple,  # noqa: F401
    Type,  # noqa: F401
    TypedDict,  # noqa: F401
    TypeVar,  # noqa: F401
    Union,  # noqa: F401
    cast,  # noqa: F401
    final,  # noqa: F401
)

if sys.version_info >= (3, 11):
    from enum import StrEnum  # noqa: F401
    from typing import (
        NotRequired,  # noqa: F401
        ParamSpec,  # noqa: F401
        Required,  # noqa: F401
        TypeGuard,  # noqa: F401
    )
else:
    _T = TypeVar("_T")

    class StrEnum(Type):  # type: ignore
        pass

    class NotRequired(Type, Generic[_T]):  # type: ignore
        pass

    class ParamSpec(Type):  # type: ignore
        args = ...
        kwargs = ...

        def __init__(*args, **kwargs) -> None:  # type: ignore
            pass

    class Required(Type, Generic[_T]):  # type: ignore
        pass

    class TypeGuard(Type, Generic[_T]):  # type: ignore
        pass

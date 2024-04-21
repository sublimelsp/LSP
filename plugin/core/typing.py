from __future__ import annotations
import sys
from enum import Enum, IntEnum, IntFlag  # noqa: F401
from typing import (  # noqa: F401
    IO,
    TYPE_CHECKING,
    Any,
    Callable,
    Deque,
    Dict,
    Generator,
    Generic,
    Iterable,
    Iterator,
    List,
    Literal,
    Mapping,
    Optional,
    Protocol,
    Sequence,
    Set,
    Tuple,
    Type,
    TypedDict,
    TypeVar,
    Union,
    cast,
    final,
)
from typing_extensions import (  # noqa: F401
    NotRequired,
    ParamSpec,
    Required,
    TypeGuard,
)

if sys.version_info >= (3, 11):
    from enum import StrEnum  # noqa: F401
else:
    class StrEnum(str, Enum):
        """
        Naive polyfill for Python 3.11's StrEnum.

        See https://docs.python.org/3.11/library/enum.html#enum.StrEnum
        """

        __format__ = str.__format__
        __str__ = str.__str__

from __future__ import annotations

from enum import Enum, IntEnum, IntFlag
from typing import (
    Any,
    Callable,
    cast,
    Deque,
    Dict,
    final,
    Generator,
    Generic,
    IO,
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
    TYPE_CHECKING,
    TypedDict,
    TypeVar,
    Union,
)
from typing_extensions import (
    NotRequired,
    ParamSpec,
    Required,
    TypeGuard,
)
import sys

if sys.version_info >= (3, 11):
    from enum import StrEnum
else:
    class StrEnum(str, Enum):
        """
        Naive polyfill for Python 3.11's StrEnum.

        See https://docs.python.org/3.11/library/enum.html#enum.StrEnum
        """

        __format__ = str.__format__
        __str__ = str.__str__

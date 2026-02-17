from __future__ import annotations

from enum import Enum
from enum import IntEnum
from enum import IntFlag
from typing import Any
from typing import Callable
from typing import cast
from typing import Deque
from typing import Dict
from typing import final
from typing import Generator
from typing import Generic
from typing import IO
from typing import Iterable
from typing import Iterator
from typing import List
from typing import Literal
from typing import Mapping
from typing import Optional
from typing import Protocol
from typing import Sequence
from typing import Set
from typing import Tuple
from typing import Type
from typing import TYPE_CHECKING
from typing import TypedDict
from typing import TypeVar
from typing import Union
from typing_extensions import NotRequired
from typing_extensions import ParamSpec
from typing_extensions import Required
from typing_extensions import TypeGuard
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

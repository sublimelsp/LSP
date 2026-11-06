# Stubs for sublime_types.py
from sublime import KindId
from typing import Mapping, Sequence
from typing_extensions import TypeAlias

Kind: TypeAlias = tuple[KindId, str, str]

Value: TypeAlias = "bool | str | int | float | list[Value] | dict[str, Value] | None"
"""
A JSON compatible value, as returned by the settings and project data APIs.
"""

ValueLike: TypeAlias = "bool | str | int | float | Sequence[ValueLike] | Mapping[str, ValueLike] | None"
"""
What the value layer accepts on the way in, where `Value` describes what it hands back. The containers are the covariant
protocols, so a `list[str]` or a `dict[str, str]` can be passed as it is.

This alias exists only in the stubs, for type checking: the real `sublime_types` module has no `ValueLike` name at
runtime, so it must be imported inside an `if TYPE_CHECKING:` block.
"""

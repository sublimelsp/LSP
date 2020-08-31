from typing import Any, Optional

BRACE: int = ...
GLOBSTAR: int = ...


def globmatch(
    filename: Any,
    patterns: Any,
    *,
    flags: int = ...,
    root_dir: Optional[Any] = ...,
    limit: Any = ...
) -> bool: ...

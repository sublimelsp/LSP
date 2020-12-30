import sys

if sys.version_info >= (3, 8, 0):

    from typing import Any
    from typing import Callable
    from typing import cast
    from typing import Deque
    from typing import Dict
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
    from typing import TypedDict
    from typing import TypeVar
    from typing import Union

else:

    def cast(typ, val):  # type: ignore
        return val

    def _make_type(name: str) -> '_TypeMeta':
        return _TypeMeta(name, (Type,), {})  # type: ignore

    class _TypeMeta(type):
        def __getitem__(self, args: 'Any') -> 'Any':
            if not isinstance(args, tuple):
                args = (args,)

            name = '{}[{}]'.format(
                str(self),
                ', '.join(map(str, args))
            )
            return _make_type(name)

        def __str__(self) -> str:
            return self.__name__

    class Type(metaclass=_TypeMeta):  # type: ignore
        pass

    class TypedDict(Type, dict):  # type: ignore
        def __init__(*args, **kwargs) -> None:  # type: ignore
            pass

    class Any(Type):  # type: ignore
        pass

    class Callable(Type):  # type: ignore
        pass

    class Deque(Type):  # type: ignore
        pass

    class Dict(Type):  # type: ignore
        pass

    class Generic(Type):  # type: ignore
        pass

    class Generator(Type):  # type: ignore
        pass

    class IO(Type):  # type: ignore
        pass

    class Iterable(Type):  # type: ignore
        pass

    class Iterator(Type):  # type: ignore
        pass

    class List(Type):  # type: ignore
        pass

    class Literal(Type):  # type: ignore
        pass

    class Mapping(Type):  # type: ignore
        pass

    class Optional(Type):  # type: ignore
        pass

    class Set(Type):  # type: ignore
        pass

    class Tuple(Type):  # type: ignore
        pass

    class Union(Type):  # type: ignore
        pass

    class Protocol(Type):  # type: ignore
        pass

    class Sequence(Type):  # type: ignore
        pass

    def TypeVar(*args, **kwargs) -> Any:  # type: ignore
        return object

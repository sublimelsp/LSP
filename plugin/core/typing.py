try:

    from typing import Any
    from typing import Callable
    from typing import Dict
    from typing import Generator
    from typing import Iterable
    from typing import Iterator
    from typing import List
    from typing import Mapping
    from typing import Optional
    from typing import Set
    from typing import Tuple
    from typing import Union
    from typing_extensions import Protocol

except ImportError:

    def _make_type(name: str) -> '_TypeMeta':
        return _TypeMeta(name, (Type,), {})

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

    class Type(metaclass=_TypeMeta):
        pass

    class Any(Type):  # type: ignore
        pass

    class Callable(Type):  # type: ignore
        pass

    class Dict(Type):  # type: ignore
        pass

    class Generator(Type):  # type: ignore
        pass

    class Iterable(Type):  # type: ignore
        pass

    class Iterator(Type):  # type: ignore
        pass

    class List(Type):  # type: ignore
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

    Protocol = object  # type: ignore

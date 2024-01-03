from LSP.plugin.core.typing import Any, Callable
from types import MethodType
import weakref


__all__ = ['weak_method']


# An implementation of weak method borrowed from sublime_lib [1]
#
# We need it to be able to weak reference bound methods as `weakref.WeakMethod` is not available in
# 3.3 runtime.
#
# The reason this is necessary is explained in the documentation of `weakref.WeakMethod`:
# > A custom ref subclass which simulates a weak reference to a bound method (i.e., a method defined
# > on a class and looked up on an instance). Since a bound method is ephemeral, a standard weak
# > reference cannot keep hold of it.
#
# [1] https://github.com/SublimeText/sublime_lib/blob/master/st3/sublime_lib/_util/weak_method.py

def weak_method(method: Callable[..., Any]) -> Callable[..., Any]:
    assert isinstance(method, MethodType)
    self_ref = weakref.ref(method.__self__)
    function_ref = weakref.ref(method.__func__)

    def wrapped(*args: Any, **kwargs: Any) -> Any:
        self = self_ref()
        fn = function_ref()
        if self is None or fn is None:
            print('[LSP.api] Error: weak_method not called due to a deleted reference', [self, fn])
            return
        return fn(self, *args, **kwargs)  # type: ignore

    return wrapped

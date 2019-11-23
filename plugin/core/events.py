try:
    from typing import Any, List, Dict, Tuple, Callable, Optional
    assert Any and List and Dict and Tuple and Callable and Optional
except ImportError:
    pass


class Events:
    def __init__(self) -> None:
        self._listener_dict = dict()  # type: Dict[str, List[Callable[..., None]]]

    def subscribe(self, key: str, listener: 'Callable') -> 'Callable':
        if key in self._listener_dict:
            self._listener_dict[key].append(listener)
        else:
            self._listener_dict[key] = [listener]
        return lambda: self.unsubscribe(key, listener)

    def unsubscribe(self, key: str, listener: 'Callable') -> None:
        if key in self._listener_dict:
            self._listener_dict[key].remove(listener)

    def publish(self, key: str, *args: 'Any') -> None:
        if key in self._listener_dict:
            for listener in self._listener_dict[key]:
                listener(*args)

    def reset(self) -> None:
        self._listener_dict = dict()


global_events = Events()

try:
    from typing import Any, List, Dict, Tuple, Callable, Optional
    assert Any and List and Dict and Tuple and Callable and Optional
except ImportError:
    pass


class Events:
    def __init__(self):
        self._listener_dict = dict()  # type: Dict[str, Callable[..., None]]

    def subscribe(self, key, listener):
        if key in self._listener_dict:
            self._listener_dict[key].append(listener)
        else:
            self._listener_dict[key] = [listener]
        return lambda: self._unsubscribe(key, listener)

    def unsubscribe(self, key, listener):
        if key in self._listener_dict:
            self._listener_dict[key].remove(listener)

    def publish(self, key, *args):
        if key in self._listener_dict:
            for listener in self._listener_dict[key]:
                listener(*args)

    def reset(self):
        self._listener_dict = dict()


global_events = Events()

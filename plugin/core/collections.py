"""
Module with additional collections.
"""
from .typing import Optional, Dict, Any
from copy import deepcopy


class DottedDict:

    __slots__ = ('_d',)

    def __init__(self, d: Optional[Dict[str, Any]] = None) -> None:
        """
        Construct a DottedDict, optionally from an existing dictionary.

        :param      d:    An existing dictionary.
        """
        self._d = {}  # type: Dict[str, Any]
        if d is not None:
            self.update(d)

    @classmethod
    def from_base_and_override(cls, base: "DottedDict", override: Optional[Dict[str, Any]]) -> "DottedDict":
        result = DottedDict(base.copy())
        if override:
            result.update(override)
        return result

    def get(self, path: Optional[str] = None) -> Any:
        """
        Get a value from the dictionary.

        :param      path:  The path, e.g. foo.bar.baz, or None.

        :returns:   The value stored at the path, or None if it doesn't exist.
                    Note that this cannot distinguish between None values and
                    paths that don't exist. If the path is None, returns the
                    entire dictionary.
        """
        if path is None:
            return self._d
        current = self._d  # type: Any
        keys = path.split('.')
        for key in keys:
            if isinstance(current, dict):
                current = current.get(key)
            else:
                return None
        return current

    def set(self, path: str, value: Any) -> None:
        """
        Set a value in the dictionary.

        :param      path:   The path, e.g. foo.bar.baz
        :param      value:  The value
        """
        current = self._d
        keys = path.split('.')
        for i in range(0, len(keys) - 1):
            key = keys[i]
            next_current = current.get(key)
            if not isinstance(next_current, dict):
                next_current = {}
                current[key] = next_current
            current = next_current
        current[keys[-1]] = value

    def remove(self, path: str) -> None:
        """
        Remove a key from the dictionary.

        :param      path:  The path, e.g. foo.bar.baz
        """
        current = self._d
        keys = path.split('.')
        for i in range(0, len(keys) - 1):
            key = keys[i]
            next_current = current.get(key)
            if not isinstance(next_current, dict):
                return
            current = next_current
        current.pop(keys[-1], None)

    def copy(self, path: Optional[str] = None) -> Any:
        """
        Get a copy of the value from the dictionary or copy of whole dictionary.

        :param      path:  The path, e.g. foo.bar.baz, or None.

        :returns:   A copy of the value stored at the path, or None if it doesn't exist.
                    Note that this cannot distinguish between None values and
                    paths that don't exist. If the path is None, returns a copy of the
                    entire dictionary.
        """
        return deepcopy(self.get(path))

    def __bool__(self) -> bool:
        """
        If this collection has at least one key-value pair, return True, else return False.
        """
        return bool(self._d)

    def __contains__(self, path: str) -> bool:
        value = self.get(path)
        return value is not None and value is not False

    def clear(self) -> None:
        """
        Remove all key-value pairs.
        """
        self._d.clear()

    def assign(self, d: Dict[str, Any]) -> None:
        """
        Overwrites the old stored dictionary with a fresh new dictionary.

        :param      d:    The new dictionary to store
        """
        self._d = d

    def update(self, d: Dict[str, Any]) -> None:
        """
        Overwrite and/or add new key-value pairs to the collection.

        :param      d:    The overriding dictionary. Can contain nested dictionaries.
        """
        for key, value in d.items():
            if isinstance(value, dict):
                self._update_recursive(value, key)
            else:
                self.set(key, value)

    def _update_recursive(self, current: Dict[str, Any], prefix: str) -> None:
        if not current:
            return self.set(prefix, current)
        for key, value in current.items():
            path = "{}.{}".format(prefix, key)
            if isinstance(value, dict):
                self._update_recursive(value, path)
            else:
                self.set(path, value)

    def __repr__(self) -> str:
        return "{}({})".format(self.__class__.__name__, repr(self._d))

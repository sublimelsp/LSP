"""
Module with additional collections.
"""
from .typing import Optional, Dict, Any, Generator
from copy import deepcopy
import sublime
import sys
import json


class DottedDict:

    __slots__ = ('_d',)

    def __init__(self, d: Optional[Dict[str, Any]] = None, process_dotted_keys_level: int = sys.maxsize) -> None:
        """
        Construct a DottedDict, optionally from an existing dictionary.

        :param      d:    An existing dictionary.
        """
        self._d = {}  # type: Dict[str, Any]
        if d is not None:
            self.update(d, process_dotted_keys_level)

    @classmethod
    def from_base_and_override(cls, base: "DottedDict", override: Optional[Dict[str, Any]]) -> "DottedDict":
        result = DottedDict(base.copy(), process_dotted_keys_level=1)
        if override:
            result.update(override, process_dotted_keys_level=1)
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

    def walk(self, path: str) -> Generator[Any, None, None]:
        current = self._d  # type: Any
        keys = path.split('.')
        for key in keys:
            if isinstance(current, dict):
                current = current.get(key)
                yield current
            else:
                yield None
                return

    def set(self, path: str, value: Any, obj: Dict[str, Any] = None, process_dotted_keys_level: int = sys.maxsize) -> Any:
        """
        Set a value in the dictionary.

        :param      path:   The path, e.g. foo.bar.baz
        :param      value:  The value
        """
        current = self._d if obj is None else obj
        keys = path.split('.') if process_dotted_keys_level > 0 else [path]
        print('set keys: {}'.format(keys))
        for i in range(0, len(keys) - 1):
            key = keys[i]
            print('set key: {}'.format(key))
            next_current = current.get(key)
            if not isinstance(next_current, dict):
                next_current = {}
                current[key] = next_current
            current = next_current
        print('set key: {}'.format(keys[-1]))
        current[keys[-1]] = value
        return value

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

    def update(self, d: Dict[str, Any], process_dotted_keys_level: int = sys.maxsize) -> None:
        """
        Overwrite and/or add new key-value pairs to the collection.

        :param      d:    The overriding dictionary. Can contain nested dictionaries.
        """
        print('--input--', json.dumps(d, indent=2))
        for key, value in d.items():
            print('key: {}, process_dotted_keys_level: {}'.format(key, process_dotted_keys_level))
            if isinstance(value, dict):
                print('update recursive...')
                dst = self.set(key, {}, self._d, process_dotted_keys_level)
                self._update_recursive(dst, value, key, process_dotted_keys_level - 1)
            else:
                self.set(key, value, self._d, process_dotted_keys_level)
        print('--dotted--', json.dumps(self._d, indent=2))

    def get_resolved(self, variables: Dict[str, str]) -> Dict[str, Any]:
        """
        Resolve a DottedDict that may potentially contain template variables like $folder.

        :param      variables:  The variables

        :returns:   A copy of the underlying dictionary, but with the variables replaced
        """
        return sublime.expand_variables(self._d, variables)

    def _update_recursive(
        self, dest_value: Dict[str, Any], current: Dict[str, Any], prefix: str, process_dotted_keys_level: int
    ) -> None:
        if not current:
            return
        for key, value in current.items():
            print('update recursive key: {}'.format(key))
            if isinstance(value, dict):
                dst = self.set(key, {}, dest_value, process_dotted_keys_level)
                self._update_recursive(dst, value, key, process_dotted_keys_level - 1)
            else:
                self.set(key, value, dest_value, process_dotted_keys_level)

    def __repr__(self) -> str:
        return "{}({})".format(self.__class__.__name__, repr(self._d))

    def __eq__(self, other: Any) -> bool:
        if not isinstance(other, DottedDict):
            return False
        return self._d == other._d

from .settings import read_commands
import unittest
from .types import Command
try:
    from typing import Any, Dict, List
    assert Any and Dict and List
except ImportError:
    pass


class SettingsTests(unittest.TestCase):

    def test_read_commands(self):
        commands = []  # type: List[Dict[str, Any]]
        commands.extend([
            {"name": "foo", "args": {"arg1": "v1"}},
            {"name": "bar"},
            {"not_name": "baz", "args": {"arg1": "v1"}},
        ])
        result = read_commands(commands)
        expected = [
            Command("foo", {"arg1": "v1"}),
            Command("baz", dict())
        ]
        self.assertListEqual(result, expected)

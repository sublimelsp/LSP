from __future__ import annotations

from LSP.plugin.core.collections import DottedDict
from typing import Any
from unittest import TestCase


class DottedDictTests(TestCase):

    def verify(self, d: DottedDict, path: str, value: Any) -> None:
        self.assertEqual(d.get(path), value)

    def test_set_and_get(self) -> None:
        d = DottedDict()
        d.set("foo", 1)
        d.set("bar", 2)
        d.set("baz", 3)
        self.verify(d, "foo", 1)
        self.verify(d, "bar", 2)
        self.verify(d, "baz", 3)
        d.set("foo.bar", "hello")
        self.verify(d, "foo.bar", "hello")
        self.assertIsNone(d.get("some.nonexistant.key"))
        d.set("foo", "world")
        self.verify(d, "foo", "world")
        d.set("foo.bar.baz", {"some": "dict"})
        self.verify(d, "foo.bar.baz.some", "dict")

    def test_does_not_expand_at_second_nesting_level(self) -> None:
        d = DottedDict({"editor.codeActionsOnSave": {"source.fixAll": "explicit"}})
        self.verify(d, "editor.codeActionsOnSave", {"source.fixAll": "explicit"})
        self.assertIsNone(d.get("editor.codeActionsOnSave.source"))

    def test_overwrite_int_with_dict(self) -> None:
        d = DottedDict({'foo.bar': 1})
        d.set('foo.bar', {
            "a": "a",
        })
        self.verify(d, "foo.bar", {"a": "a"})

    def test_overwrite_dict_with_dict(self) -> None:
        d = DottedDict({'foo.bar': {'a': 'a'}})
        d.set('foo.bar', {
            "b": "b",
        })
        self.verify(d, "foo.bar", {"b": "b"})

    def test_remove(self) -> None:
        d = DottedDict()
        d.set("foo", "asdf")
        self.assertIn("foo", d)
        d.remove("foo")
        self.assertNotIn("foo", d)
        self.assertIsNone(d.get("foo"))
        d.set("foo.bar", {"baz": "qux"})
        self.verify(d, "foo.bar", {"baz": "qux"})
        self.verify(d, "foo", {"bar": {"baz": "qux"}})
        d.set("foo.bar.baz", "qux")
        self.verify(d, "foo.bar", {"baz": "qux"})
        self.verify(d, "foo", {"bar": {"baz": "qux"}})
        d.set("foo.hello", "world")
        d.remove("foo.bar")
        self.verify(d, "foo", {"hello": "world"})

    def test_assign(self) -> None:
        d = DottedDict()
        d.assign({
            "a": "b",
            "c": {
                "x": "a",
                "y": "b"
            },
            "d": {
                "e": {
                    "f": {
                        "a": "b",
                        "c": "d"
                    }
                }
            }
        })
        self.verify(d, "a", "b")
        self.verify(d, "c.x", "a")
        self.verify(d, "c.y", "b")
        self.verify(d, "d.e.f.a", "b")
        self.verify(d, "d.e.f.c", "d")
        self.verify(d, "d.e.f", {"a": "b", "c": "d"})
        self.verify(d, "d.e", {"f": {"a": "b", "c": "d"}})
        self.verify(d, "d", {"e": {"f": {"a": "b", "c": "d"}}})

    def test_update(self) -> None:
        d = DottedDict()
        d.set("foo.bar.a", "a")
        d.set("foo.bar.b", "b")
        d.set("foo.bar.c", "c")
        self.verify(d, "foo.bar", {"a": "a", "b": "b", "c": "c"})
        d.update({
            "foo": {
                "bar": {
                    "a": "x",
                    "b": "y"
                }
            }
        })
        self.verify(d, "foo.bar", {"a": "x", "b": "y", "c": "c"})

    def test_as_dict(self) -> None:
        d = DottedDict()
        d.set("foo.bar.baz", 1)
        d.set("foo.bar.qux", "asdf")
        d.set("foo.bar.a", "b")
        d.set("foo.b.x", "c")
        d.set("foo.b.y", "d")
        self.assertEqual(d.get(), {
            "foo": {
                "bar": {
                    "baz": 1,
                    "qux": "asdf",
                    "a": "b"
                },
                "b": {
                    "x": "c",
                    "y": "d"
                }
            }
        })
        d.clear()
        self.assertEqual(d.get(), {})

    def test_dunder_bool(self) -> None:
        d = DottedDict({"a": {"b": {"c": {"x": "x", "y": "y"}}}})
        self.assertTrue(d)
        d.clear()
        self.assertFalse(d)
        d.update({"a": {"b": {"x": 1, "y": 2}}})
        self.assertTrue(d)
        self.verify(d, "a.b.x", 1)
        self.verify(d, "a.b.y", 2)
        d.clear()
        self.assertFalse(d)

    def test_copy_whole(self) -> None:
        d = DottedDict({"a": {"b": {"c": {"x": "x", "y": "y"}}}})
        d_copy = d.copy()
        d_copy['a'] = None
        self.assertNotEqual(d.get()['a'], d_copy['a'])

    def test_copy_partial(self) -> None:
        d = DottedDict({"a": {"b": {"c": 'd'}}})
        d_copy = d.copy('a.b')
        self.assertEqual(d_copy['c'], 'd')
        d_copy['c'] = None
        self.assertNotEqual(d.get('a.b.c'), d_copy['c'])

    def test_update_empty_dict(self) -> None:
        d = DottedDict({})
        d.update({"a": {}})
        self.assertEqual(d.get(), {"a": {}})
        d.update({"a": {"b": {}}})
        self.assertEqual(d.get(), {"a": {"b": {}}})

    def test_from_base_and_override(self) -> None:
        base = DottedDict({
            "yaml.schemas": {}
        })
        override = {
            "yaml.schemas": {
                "http://foo.com/bar.json": "**/*.json"
            }
        }
        result = DottedDict.from_base_and_override(base, override)
        self.assertEqual(
            result.get(None),
            {
                "yaml": {
                    "schemas": {
                        "http://foo.com/bar.json": "**/*.json"
                    }
                }
            }
        )

    def test_update_with_dicts(self) -> None:
        base = {
            "settings": {
                "yaml.schemas": {}
            }
        }
        overrides = {
            "yaml.schemas": {
                "http://foo.com/bar.json": "**/*.json"
            }
        }
        settings = DottedDict(base.get("settings", {}))
        settings.update(overrides)
        self.assertEqual(settings.get(), {
            "yaml": {
                "schemas": {
                    "http://foo.com/bar.json": "**/*.json"
                }
            }
        })

from __future__ import annotations

from LSP.plugin.core.types import ClientConfig
from LSP.plugin.core.types import DottedDict
from LSP.plugin.core.views import get_uri_and_position_from_location
from LSP.plugin.core.views import to_encoded_filename
from os import environ
from os.path import dirname
from os.path import pathsep
from typing import Any
from unittesting import DeferrableTestCase
import sublime
import sys
import unittest

test_file_path = dirname(__file__) + "/testfile.txt"


def read_client_config(name: str, d: dict[str, Any]) -> ClientConfig:
    return ClientConfig.from_dict(name, d)


def update_client_config(external_config: ClientConfig, user_override_config: dict[str, Any]) -> ClientConfig:
    return ClientConfig.from_config(external_config, user_override_config)


class ConfigParsingTests(DeferrableTestCase):

    def test_can_parse_old_client_settings(self):
        settings = {
            "command": ["pyls"],
            "scopes": ["text.html.vue"],
            "syntaxes": ["Packages/Python/Python.sublime-syntax"],  # it should use this one
            "languageId": "java"
        }
        config = read_client_config("pyls", settings)
        self.assertEqual(config.selector, "source.python")
        self.assertEqual(config.priority_selector, "(text.html.vue)")

    def test_can_parse_client_settings_with_languages(self):
        settings = {
            "command": ["pyls"],
            # Check that "selector" will be "source.python"
            "languages": [{"languageId": "python"}]
        }
        config = read_client_config("pyls", settings)
        self.assertEqual(config.selector, "(source.python)")
        self.assertEqual(config.priority_selector, "(source.python)")

    def test_can_parse_settings_with_selector(self):
        settings = {
            "command": ["pyls"],
            "selector": "source.python"
        }
        config = read_client_config("pyls", settings)
        self.assertEqual(config.selector, "source.python")
        self.assertEqual(config.priority_selector, "source.python")

    def test_can_update_config(self):
        settings = {
            "command": ["pyls"],
            "document_selector": "source.python",
            "languageId": "python"
        }
        config = read_client_config("pyls", settings)
        config = update_client_config(config, {"enabled": True})
        self.assertEqual(config.enabled, True)

    def test_can_read_experimental_capabilities(self):
        experimental_capabilities = {
            "foo": 1,
            "bar": True,
            "baz": "abc"
        }
        settings = {
            "command": ["pyls"],
            "document_selector": "source.python",
            "languageId": "python",
            "experimental_capabilities": experimental_capabilities
        }
        config = read_client_config("pyls", settings)
        self.assertEqual(config.experimental_capabilities, experimental_capabilities)

    def test_transport_config_extends_env_path(self):
        settings = {
            "command": ["pyls"],
            "selector": "source.python",
            "env": {
                "PATH": "/a/b/"
            }
        }
        config = read_client_config("pyls", settings)
        transport_config = config.resolve_transport_config({})
        original_path = environ.copy()['PATH']
        resolved_path = transport_config.env['PATH']
        self.assertEqual(resolved_path, f'/a/b/{pathsep}{original_path}')

    def test_list_in_environment(self):
        settings = {
            "command": ["pyls"],
            "selector": "source.python",
            "env": {
                "FOO": ["C:/hello", "X:/there", "Y:/$foobar"],
                "BAR": "baz"
            }
        }
        config = read_client_config("pyls", settings)
        resolved = config.resolve_transport_config({"foobar": "asdf"})
        if sublime.platform() == "windows":
            self.assertEqual(resolved.env["FOO"], "C:/hello;X:/there;Y:/asdf")
        else:
            self.assertEqual(resolved.env["FOO"], "C:/hello:X:/there:Y:/asdf")
        self.assertEqual(resolved.env["BAR"], "baz")

    def test_disabled_capabilities(self):
        settings = {
            "command": ["pyls"],
            "selector": "source.python",
            "disabled_capabilities": {
                "colorProvider": True,
                "completionProvider": {"triggerCharacters": True},
                "codeActionProvider": True
            }
        }
        config = read_client_config("pyls", settings)
        self.assertTrue(config.is_disabled_capability("colorProvider"))
        # If only a sub path is disabled, the entire capability should not be disabled as a whole
        self.assertFalse(config.is_disabled_capability("completionProvider"))
        # This sub path should be disabled
        self.assertTrue(config.is_disabled_capability("completionProvider.triggerCharacters"))
        # But not this sub path
        self.assertFalse(config.is_disabled_capability("completionProvider.resolveProvider"))
        # The entire codeActionProvider is disabled
        self.assertTrue(config.is_disabled_capability("codeActionProvider"))
        # If codeActionProvider is disabled, all of its sub paths should be disabled as well
        self.assertTrue(config.is_disabled_capability("codeActionProvider.codeActionKinds"))
        # This one should be enabled
        self.assertFalse(config.is_disabled_capability("definitionProvider"))

    def test_filter_out_disabled_capabilities_ignore_partially(self):
        settings = {
            "command": ["pyls"],
            "selector": "source.python",
            "disabled_capabilities": {"completionProvider": {"triggerCharacters": True}}
        }
        config = read_client_config("pyls", settings)
        capability_path = "completionProvider"
        options = {"triggerCharacters": ["!"], "resolveProvider": True}
        options = config.filter_out_disabled_capabilities(capability_path, options)
        self.assertNotIn("triggerCharacters", options)
        self.assertIn("resolveProvider", options)

    def test_exposes_unknown_root_keys(self):
        settings = {
            "unknown": {
                "foo": 1
            },
        }
        config = read_client_config("test", settings)
        self.assertIn("unknown", config)
        self.assertNotIn("else", config)
        self.assertEqual(config.unknown, settings['unknown'])
        self.assertEqual(config['unknown'], settings['unknown'])

    def test_shallow_merges_overrides_for_unknown_root_keys(self):
        settings = {
            "unknown": {
                "foo": 1
            },
        }
        overriddes = {
            "unknown": {
                "bar": 2
            }
        }
        config = update_client_config(read_client_config("test", settings), overriddes)
        self.assertEqual(config.unknown, overriddes['unknown'])

    def test_prefers_native_keys_through_attribute_access(self):
        settings = {
            "settings": {
                "setting1": 1
            },
        }
        config = read_client_config("test", settings)
        self.assertIsInstance(config.settings, DottedDict)

    def test_only_exposes_unknown_keys_through_subscription_access(self):
        settings = {
            "settings": {
                "setting1": 1
            },
            "unknown": {
                "foo": 1
            },
        }
        config = read_client_config("test", settings)
        self.assertNotIn('settings', config)
        self.assertIn('unknown', config)
        self.assertEqual(config['unknown'], settings['unknown'])

    @unittest.skipIf(sys.platform.startswith("win"), "requires non-Windows")
    def test_path_maps(self):
        config = read_client_config("asdf", {
            "command": ["asdf"],
            "selector": "source.foo",
            "path_maps": [
                {
                    "local": "/home/user/projects/myproject",
                    "remote": "/workspace"
                },
                {
                    "local": "/home/user/projects/another",
                    "remote": "/workspace2"
                }
            ]
        })
        uri = config.map_client_path_to_server_uri("/home/user/projects/myproject/file.js")
        self.assertEqual(uri, "file:///workspace/file.js")
        uri = config.map_client_path_to_server_uri("/home/user/projects/another/foo.js")
        self.assertEqual(uri, "file:///workspace2/foo.js")
        uri = config.map_client_path_to_server_uri("/some/path/with/no/mapping.py")
        self.assertEqual(uri, "file:///some/path/with/no/mapping.py")
        path = config.map_server_uri_to_client_path("file:///workspace/bar.html")
        self.assertEqual(path, "/home/user/projects/myproject/bar.html")
        path = config.map_server_uri_to_client_path("file:///workspace2/style.css")
        self.assertEqual(path, "/home/user/projects/another/style.css")

        # Test to_encoded_filename
        uri, position = get_uri_and_position_from_location({
            'uri': 'file:///foo/bar',
            'range': {'start': {'line': 0, 'character': 5}}
        })  # type: ignore
        path = config.map_server_uri_to_client_path(uri)
        self.assertEqual(to_encoded_filename(path, position), '/foo/bar:1:6')
        uri, position = get_uri_and_position_from_location({
                'targetUri': 'file:///foo/bar',
                'targetSelectionRange': {'start': {'line': 1234, 'character': 4321}}
            })  # type: ignore
        path = config.map_server_uri_to_client_path(uri)
        self.assertEqual(to_encoded_filename(path, position), '/foo/bar:1235:4322')

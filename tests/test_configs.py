from unittesting import DeferrableTestCase
import unittest
import sublime
from os.path import dirname
from LSP.plugin.core.settings import client_configs, read_client_config, update_client_config
from LSP.plugin.core.registry import windows

test_file_path = dirname(__file__) + "/testfile.txt"


class ConfigParsingTests(DeferrableTestCase):

    def test_can_parse_old_client_settings(self):
        settings = {
            "command": ["pyls"],
            "scopes": ["source.python"],
            "syntaxes": ["Packages/Python/Python.sublime-syntax"],
            "languageId": "python"
        }
        config = read_client_config("pyls", settings)
        self.assertEqual(len(config.languages), 1)
        self.assertEqual(config.languages[0].document_selector, "source.python")

    def test_can_parse_client_settings_with_languages(self):
        settings = {
            "command": ["pyls"],
            # Check that "document_selector" will be "source.python"
            "languages": [{"languageId": "python"}]
        }
        config = read_client_config("pyls", settings)
        self.assertEqual(len(config.languages), 1)
        self.assertEqual(config.languages[0].document_selector, "source.python")
        self.assertEqual(config.languages[0].feature_selector, "source.python")

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

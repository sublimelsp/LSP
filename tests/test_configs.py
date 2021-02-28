from LSP.plugin.core.settings import read_client_config, update_client_config
from os.path import dirname
from unittesting import DeferrableTestCase

test_file_path = dirname(__file__) + "/testfile.txt"


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
        # The entire codeActionProvider is disabld
        self.assertTrue(config.is_disabled_capability("codeActionProvider"))
        # If codeActionProvider is disabled, all of its sub paths should be disabled as well
        self.assertTrue(config.is_disabled_capability("codeActionProvider.codeActionKinds"))
        # This one should be enabled
        self.assertFalse(config.is_disabled_capability("definitionProvider"))

    def test_filter_disabled_capabilities_ignore_partially(self):
        settings = {
            "command": ["pyls"],
            "selector": "source.python",
            "disabled_capabilities": {"completionProvider": {"triggerCharacters": True}}
        }
        config = read_client_config("pyls", settings)
        capability_path = "completionProvider"
        options = {"triggerCharacters": ["!"], "resolveProvider": True}
        self.assertFalse(config.filter_disabled_capabilities(capability_path, options))
        self.assertNotIn("triggerCharacters", options)
        self.assertIn("resolveProvider", options)

    def test_filter_disabled_capabilities_ignore_fully(self):
        settings = {
            "command": ["pyls"],
            "selector": "source.python",
            "disabled_capabilities": {"codeActionProvider": True}
        }
        config = read_client_config("pyls", settings)
        capability_path = "codeActionProvider"
        options = {"codeActionKinds": [], "resolveProvider": True}
        self.assertTrue(config.filter_disabled_capabilities(capability_path, options))

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
                },
                {
                    "local": "C:/Documents",
                    "remote": "/workspace3"
                }
            ]
        })
        uri = config.map_client_path_to_server_uri("/home/user/projects/myproject/file.js")
        self.assertEqual(uri, "file:///workspace/file.js")
        uri = config.map_client_path_to_server_uri("/home/user/projects/another/foo.js")
        self.assertEqual(uri, "file:///workspace2/foo.js")
        uri = config.map_client_path_to_server_uri("C:/Documents/bar.ts")
        self.assertEqual(uri, "file:///workspace3/bar.ts")
        uri = config.map_client_path_to_server_uri("/some/path/with/no/mapping.py")
        self.assertEqual(uri, "file:///some/path/with/no/mapping.py")
        path = config.map_server_uri_to_client_path("file:///workspace/bar.html")
        self.assertEqual(path, "/home/user/projects/myproject/bar.html")
        path = config.map_server_uri_to_client_path("file:///workspace2/style.css")
        self.assertEqual(path, "/home/user/projects/another/style.css")
        path = config.map_server_uri_to_client_path("file:///workspace3/bar.ts")
        self.assertEqual(path, "C:/Documents/bar.ts")

        # FIXME: What if the server is running on a Windows VM,
        # but locally we are running Linux?
        path = config.map_server_uri_to_client_path("file:///c%3A/dir%20ectory/file.txt")
        self.assertEqual(path, "/c:/dir ectory/file.txt")

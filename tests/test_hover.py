from unittesting import DeferrableTestCase
import sublime
from os.path import dirname
from LSP.plugin.hover import _test_contents
from LSP.plugin.core.types import ClientConfig, ClientStates, LanguageConfig
from LSP.plugin.core.test_session import TestClient
from LSP.plugin.core.sessions import Session
from LSP.plugin.core.registry import windows  # , session_for_view
from LSP.plugin.core.settings import client_configs

test_file_path = dirname(__file__) + "/testfile.txt"

ORIGINAL_CONTENT = """Hello Wrld"""

EXPECTED_CONTENT = """<dom-module id="some-thing">
<template>
    <style></style>
</template>
</dom-module>"""


class LspHoverCommandTests(DeferrableTestCase):

    def setUp(self):
        self.view = sublime.active_window().open_file(test_file_path)

    def test_hover_info(self):

        yield 100  # wait for file to be open
        self.view.run_command('insert', {"characters": ORIGINAL_CONTENT})

        wm = windows.lookup(self.view.window())
        test_language = LanguageConfig("test", ["text.plain"], ["Plain text"])
        text_config = ClientConfig("test", [], None, languages=[test_language],)
        client_configs.add_external_config(text_config)
        client_configs.update_configs()
        wm._configs.all.append(text_config)

        session = Session(text_config, dirname(__file__), TestClient())
        session.state = ClientStates.READY
        wm._sessions[text_config.name] = session

        # session = session_for_view(self.view)
        # self.assertIsNotNone(session)
        # self.assertTrue(session.has_capability('hoverProvider'))

        self.view.run_command('lsp_hover', {'point': 3})

        # popup should be visible eventually
        yield self.view.is_popup_visible()

        last_content = _test_contents[-1]
        self.assertTrue("greeting" in last_content)

    def tearDown(self):
        if self.view:
            self.view.set_scratch(True)
            self.view.window().focus_view(self.view)
            self.view.window().run_command("close_file")

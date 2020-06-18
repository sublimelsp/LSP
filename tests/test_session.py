from LSP.plugin.core.protocol import Error
from LSP.plugin.core.protocol import TextDocumentSyncKindFull, TextDocumentSyncKindNone, TextDocumentSyncKindIncremental
from LSP.plugin.core.protocol import WorkspaceFolder
from LSP.plugin.core.rpc import Logger
from LSP.plugin.core.sessions import get_initialize_params
from LSP.plugin.core.sessions import Manager
from LSP.plugin.core.sessions import Session
from LSP.plugin.core.types import ClientConfig
from LSP.plugin.core.typing import Any, Optional, Generator
from test_mocks import TEST_CONFIG
import sublime
import unittest
import unittest.mock


class MockManager(Manager):

    def __init__(self, window: sublime.Window) -> None:
        self._window = window

    def window(self) -> sublime.Window:
        return self._window

    def sessions(self, view: sublime.View, capability: Optional[str] = None) -> Generator[Session, None, None]:
        pass

    def start_async(self, configuration: ClientConfig, initiating_view: sublime.View) -> None:
        pass

    def on_post_exit_async(self, session: Session, exit_code: int, exception: Optional[Exception]) -> None:
        pass

    def on_post_initialize(self, session: Session) -> None:
        pass


class MockLogger(Logger):

    def stderr_message(self, message: str) -> None:
        pass

    def outgoing_response(self, request_id: Any, params: Any) -> None:
        pass

    def outgoing_error_response(self, request_id: Any, error: Error) -> None:
        pass

    def outgoing_request(self, request_id: int, method: str, params: Any, blocking: bool) -> None:
        pass

    def outgoing_notification(self, method: str, params: Any) -> None:
        pass

    def incoming_response(self, request_id: int, params: Any, is_error: bool, blocking: bool) -> None:
        pass

    def incoming_request(self, request_id: Any, method: str, params: Any) -> None:
        pass

    def incoming_notification(self, method: str, params: Any, unhandled: bool) -> None:
        pass


class SessionTest(unittest.TestCase):

    def test_experimental_capabilities(self) -> None:
        wf = WorkspaceFolder.from_path("/foo/bar/baz")
        params = get_initialize_params(
            {},
            [wf],
            ClientConfig(name="test", binary_args=[""], languages=[], tcp_port=None, experimental_capabilities=None))
        self.assertNotIn("experimental", params["capabilities"])

        params = get_initialize_params(
            {},
            [wf],
            ClientConfig(name="test", binary_args=[""], languages=[], tcp_port=None, experimental_capabilities={}))
        self.assertIn("experimental", params["capabilities"])
        self.assertEqual(params["capabilities"]["experimental"], {})

        experimental_capabilities = {
            "foo": 1,
            "bar": True,
            "baz": "abc"
        }
        config = ClientConfig(
            name="test",
            binary_args=[""],
            languages=[],
            tcp_port=None,
            experimental_capabilities=experimental_capabilities
        )
        params = get_initialize_params({}, [wf], config)
        self.assertIn("experimental", params["capabilities"])
        self.assertEqual(params["capabilities"]["experimental"], experimental_capabilities)

    def test_initialize_params(self) -> None:
        wf = WorkspaceFolder.from_path("/foo/bar/baz")
        params = get_initialize_params(
            {}, [wf], ClientConfig(name="test", binary_args=[""], languages=[], tcp_port=None, init_options=None))
        self.assertNotIn("initializationOptions", params)
        params = get_initialize_params(
            {}, [wf], ClientConfig(name="test", binary_args=[""], languages=[], tcp_port=None, init_options={}))
        self.assertIn("initializationOptions", params)
        self.assertEqual(params["initializationOptions"], {})
        params = get_initialize_params(
            {}, [wf], ClientConfig(
                name="test", binary_args=[""], languages=[], tcp_port=None, init_options={"foo": "bar"}))
        self.assertIn("initializationOptions", params)
        self.assertEqual(params["initializationOptions"], {"foo": "bar"})

    def test_document_sync_capabilities(self) -> None:
        manager = MockManager(sublime.active_window())
        session = Session(manager=manager, logger=MockLogger(), workspace_folders=[], config=TEST_CONFIG,
                          plugin_class=None)
        session.capabilities.assign({
            'textDocumentSync': {
                "openClose": True,
                "change": TextDocumentSyncKindFull,
                "save": True}})  # A boolean with value true means "send didSave"
        self.assertTrue(session.should_notify_did_open())
        self.assertTrue(session.should_notify_did_close())
        self.assertEqual(session.text_sync_kind(), TextDocumentSyncKindFull)
        self.assertTrue(session.should_notify_did_change())
        self.assertFalse(session.should_notify_will_save())
        self.assertEqual(session.should_notify_did_save(), (True, False))

        session.capabilities.assign({
            'textDocumentSync': {
                "openClose": False,
                "change": TextDocumentSyncKindNone,
                "save": {},  # An empty dict means "send didSave"
                "willSave": True,
                "willSaveWaitUntil": False}})
        self.assertFalse(session.should_notify_did_open())
        self.assertFalse(session.should_notify_did_close())
        self.assertEqual(session.text_sync_kind(), TextDocumentSyncKindNone)
        self.assertFalse(session.should_notify_did_change())
        self.assertTrue(session.should_notify_will_save())
        self.assertEqual(session.should_notify_did_save(), (True, False))
        # Nested capabilities.
        self.assertTrue(session.has_capability('textDocumentSync.change'))
        self.assertTrue(session.has_capability('textDocumentSync.save'))
        self.assertTrue(session.has_capability('textDocumentSync.willSave'))
        self.assertFalse(session.has_capability('textDocumentSync.willSaveUntil'))
        self.assertFalse(session.has_capability('textDocumentSync.aintthere'))

        session.capabilities.assign({
            'textDocumentSync': {
                "openClose": False,
                "change": TextDocumentSyncKindIncremental,
                "save": {"includeText": True},
                "willSave": False,
                "willSaveWaitUntil": True}})
        self.assertFalse(session.should_notify_did_open())
        self.assertFalse(session.should_notify_did_close())
        self.assertEqual(session.text_sync_kind(), TextDocumentSyncKindIncremental)
        self.assertTrue(session.should_notify_did_change())
        self.assertFalse(session.should_notify_will_save())
        self.assertEqual(session.should_notify_did_save(), (True, True))

        session.capabilities.assign({'textDocumentSync': TextDocumentSyncKindIncremental})
        self.assertTrue(session.should_notify_did_open())
        self.assertTrue(session.should_notify_did_close())
        self.assertEqual(session.text_sync_kind(), TextDocumentSyncKindIncremental)
        self.assertTrue(session.should_notify_did_change())
        self.assertFalse(session.should_notify_will_save())  # old-style text sync will never send willSave
        self.assertEqual(session.should_notify_did_save(), (False, False))

        session.capabilities.assign({'textDocumentSync': TextDocumentSyncKindNone})
        self.assertFalse(session.should_notify_did_open())
        self.assertFalse(session.should_notify_did_close())
        self.assertEqual(session.text_sync_kind(), TextDocumentSyncKindNone)
        self.assertFalse(session.should_notify_did_change())
        self.assertFalse(session.should_notify_will_save())
        self.assertEqual(session.should_notify_did_save(), (False, False))

        session.capabilities.assign({
            'textDocumentSync': {
                "openClose": True,
                "save": False,
                "change": TextDocumentSyncKindIncremental}})
        self.assertTrue(session.should_notify_did_open())
        self.assertTrue(session.should_notify_did_close())
        self.assertEqual(session.text_sync_kind(), TextDocumentSyncKindIncremental)
        self.assertTrue(session.should_notify_did_change())
        self.assertFalse(session.should_notify_will_save())
        self.assertEqual(session.should_notify_did_save(), (False, False))

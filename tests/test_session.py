from LSP.plugin.core.collections import DottedDict
from LSP.plugin.core.protocol import Diagnostic
from LSP.plugin.core.protocol import DocumentUri
from LSP.plugin.core.protocol import Error
from LSP.plugin.core.protocol import TextDocumentSyncKind
from LSP.plugin.core.sessions import get_initialize_params
from LSP.plugin.core.sessions import Logger
from LSP.plugin.core.sessions import Manager
from LSP.plugin.core.sessions import Session
from LSP.plugin.core.types import ClientConfig
from LSP.plugin.core.typing import Any, Optional, Generator, List, Dict
from LSP.plugin.core.workspace import WorkspaceFolder
from test_mocks import TEST_CONFIG
import sublime
import unittest
import unittest.mock
import weakref


class MockManager(Manager):

    def __init__(self, window: sublime.Window) -> None:
        self._window = window

    def window(self) -> sublime.Window:
        return self._window

    def sessions(self, view: sublime.View, capability: Optional[str] = None) -> Generator[Session, None, None]:
        pass

    def get_project_path(self, file_name: str) -> Optional[str]:
        return None

    def should_ignore_diagnostics(self, uri: DocumentUri) -> Optional[str]:
        return None

    def start_async(self, configuration: ClientConfig, initiating_view: sublime.View) -> None:
        pass

    def on_post_exit_async(self, session: Session, exit_code: int, exception: Optional[Exception]) -> None:
        pass

    def on_diagnostics_updated(self) -> None:
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


class MockSessionBuffer:

    def __init__(self, session: Session, mock_uri: str, mock_language_id: str) -> None:
        self.session = session
        self.session_views = weakref.WeakSet()
        self.mock_uri = mock_uri
        self.mock_language_id = mock_language_id

    def get_uri(self) -> Optional[DocumentUri]:
        return self.mock_uri

    def get_language_id(self) -> Optional[str]:
        return self.mock_language_id

    def register_capability_async(
        self,
        registration_id: str,
        capability_path: str,
        registration_path: str,
        options: Dict[str, Any]
    ) -> None:
        pass

    def unregister_capability_async(
        self,
        registration_id: str,
        capability_path: str,
        registration_path: str
    ) -> None:
        pass

    def on_diagnostics_async(self, raw_diagnostics: List[Diagnostic], version: Optional[int]) -> None:
        pass


class SessionTest(unittest.TestCase):

    def test_experimental_capabilities(self) -> None:
        wf = WorkspaceFolder.from_path("/foo/bar/baz")
        params = get_initialize_params(
            {},
            [wf],
            ClientConfig(name="test", command=[""], selector="", tcp_port=None, experimental_capabilities=None))
        self.assertNotIn("experimental", params["capabilities"])

        params = get_initialize_params(
            {},
            [wf],
            ClientConfig(name="test", command=[""], selector="", tcp_port=None, experimental_capabilities={}))
        self.assertIn("experimental", params["capabilities"])
        self.assertEqual(params["capabilities"]["experimental"], {})

        experimental_capabilities = {
            "foo": 1,
            "bar": True,
            "baz": "abc"
        }
        config = ClientConfig(
            name="test",
            command=[""],
            selector="",
            tcp_port=None,
            experimental_capabilities=experimental_capabilities
        )
        params = get_initialize_params({}, [wf], config)
        self.assertIn("experimental", params["capabilities"])
        self.assertEqual(params["capabilities"]["experimental"], experimental_capabilities)

    def test_initialize_params(self) -> None:
        wf = WorkspaceFolder.from_path("/foo/bar/baz")
        params = get_initialize_params(
            {}, [wf], ClientConfig(name="test", command=[""], selector="", tcp_port=None, init_options=DottedDict()))
        self.assertIn("initializationOptions", params)
        self.assertEqual(params["initializationOptions"], {})
        params = get_initialize_params(
            {}, [wf], ClientConfig(
                name="test", command=[""], selector="", tcp_port=None, init_options=DottedDict({"foo": "bar"})))
        self.assertIn("initializationOptions", params)
        self.assertEqual(params["initializationOptions"], {"foo": "bar"})

    def test_document_sync_capabilities(self) -> None:
        manager = MockManager(sublime.active_window())
        session = Session(manager=manager, logger=MockLogger(), workspace_folders=[], config=TEST_CONFIG,
                          plugin_class=None)
        session.capabilities.assign({
            'textDocumentSync': {
                "openClose": True,
                "change": TextDocumentSyncKind.Full,
                "save": True}})  # A boolean with value true means "send didSave"
        self.assertTrue(session.should_notify_did_open())
        self.assertTrue(session.should_notify_did_close())
        self.assertEqual(session.text_sync_kind(), TextDocumentSyncKind.Full)
        self.assertFalse(session.should_notify_will_save())
        self.assertEqual(session.should_notify_did_save(), (True, False))

        session.capabilities.assign({
            'textDocumentSync': {
                "didOpen": {},
                "didClose": {},
                "change": TextDocumentSyncKind.Full,
                "save": True}})  # A boolean with value true means "send didSave"
        self.assertTrue(session.should_notify_did_open())
        self.assertTrue(session.should_notify_did_close())
        self.assertEqual(session.text_sync_kind(), TextDocumentSyncKind.Full)
        self.assertFalse(session.should_notify_will_save())
        self.assertEqual(session.should_notify_did_save(), (True, False))

        session.capabilities.assign({
            'textDocumentSync': {
                "openClose": False,
                "change": TextDocumentSyncKind.None_,
                "save": {},  # An empty dict means "send didSave"
                "willSave": True,
                "willSaveWaitUntil": False}})
        self.assertFalse(session.should_notify_did_open())
        self.assertFalse(session.should_notify_did_close())
        self.assertEqual(session.text_sync_kind(), TextDocumentSyncKind.None_)
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
                "change": TextDocumentSyncKind.Incremental,
                "save": {"includeText": True},
                "willSave": False,
                "willSaveWaitUntil": True}})
        self.assertFalse(session.should_notify_did_open())
        self.assertFalse(session.should_notify_did_close())
        self.assertEqual(session.text_sync_kind(), TextDocumentSyncKind.Incremental)
        self.assertFalse(session.should_notify_will_save())
        self.assertEqual(session.should_notify_did_save(), (True, True))

        session.capabilities.assign({'textDocumentSync': TextDocumentSyncKind.Incremental})
        self.assertTrue(session.should_notify_did_open())
        self.assertTrue(session.should_notify_did_close())
        self.assertEqual(session.text_sync_kind(), TextDocumentSyncKind.Incremental)
        self.assertFalse(session.should_notify_will_save())  # old-style text sync will never send willSave
        # old-style text sync will always send didSave
        self.assertEqual(session.should_notify_did_save(), (True, False))

        session.capabilities.assign({'textDocumentSync': TextDocumentSyncKind.None_})
        self.assertTrue(session.should_notify_did_open())  # old-style text sync will always send didOpen
        self.assertTrue(session.should_notify_did_close())  # old-style text sync will always send didClose
        self.assertEqual(session.text_sync_kind(), TextDocumentSyncKind.None_)
        self.assertFalse(session.should_notify_will_save())
        self.assertEqual(session.should_notify_did_save(), (True, False))

        session.capabilities.assign({
            'textDocumentSync': {
                "openClose": True,
                "save": False,
                "change": TextDocumentSyncKind.Incremental}})
        self.assertTrue(session.should_notify_did_open())
        self.assertTrue(session.should_notify_did_close())
        self.assertEqual(session.text_sync_kind(), TextDocumentSyncKind.Incremental)
        self.assertFalse(session.should_notify_will_save())
        self.assertEqual(session.should_notify_did_save(), (False, False))

    def test_get_session_buffer_for_uri_with_nonfiles(self) -> None:
        manager = MockManager(sublime.active_window())
        session = Session(manager=manager, logger=MockLogger(), workspace_folders=[], config=TEST_CONFIG,
                          plugin_class=None)
        original = MockSessionBuffer(session, "some-scheme://whatever", "somelang")
        session.register_session_buffer_async(original)
        sb = session.get_session_buffer_for_uri_async("some-scheme://whatever")
        self.assertIsNotNone(sb)
        assert sb
        self.assertEqual(sb.get_language_id(), "somelang")
        self.assertEqual(sb.get_uri(), "some-scheme://whatever")

    def test_get_session_buffer_for_uri_with_files(self) -> None:
        # todo: write windows-only test
        pass

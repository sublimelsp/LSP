from LSP.plugin.core.protocol import TextDocumentSyncKindFull, TextDocumentSyncKindNone, TextDocumentSyncKindIncremental
from LSP.plugin.core.protocol import WorkspaceFolder
from LSP.plugin.core.sessions import create_session, Session, get_initialize_params
from LSP.plugin.core.types import ClientConfig
from LSP.plugin.core.types import Settings
from LSP.plugin.core.typing import Optional
from test_mocks import MockClient
from test_mocks import TEST_CONFIG
from test_mocks import TEST_LANGUAGE
import sublime
import unittest
import unittest.mock


class SessionTest(unittest.TestCase):

    def assert_if_none(self, session: Optional[Session]) -> Session:
        self.assertIsNotNone(session)
        assert session  # mypy
        return session

    def make_session(self, bootstrap_client, on_pre_initialize=None, on_post_initialize=None,
                     on_post_exit=None) -> Session:
        project_path = "/"
        folders = [WorkspaceFolder.from_path(project_path)]
        return self.assert_if_none(
            create_session(
                config=TEST_CONFIG,
                workspace_folders=folders,
                env=dict(),
                settings=Settings(),
                bootstrap_client=bootstrap_client,
                on_pre_initialize=on_pre_initialize,
                on_post_initialize=on_post_initialize,
                on_post_exit=on_post_exit))

    def test_experimental_capabilities(self) -> None:
        wf = WorkspaceFolder.from_path("/foo/bar/baz")
        params = get_initialize_params(
            [wf], ClientConfig(name="test", binary_args=[""], languages=[], tcp_port=None,
                               experimental_capabilities=None))
        self.assertNotIn("experimental", params["capabilities"])

        params = get_initialize_params(
            [wf], ClientConfig(name="test", binary_args=[""], languages=[], tcp_port=None,
                               experimental_capabilities={}))
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
        params = get_initialize_params([wf], config)
        self.assertIn("experimental", params["capabilities"])
        self.assertEqual(params["capabilities"]["experimental"], experimental_capabilities)

    def test_initialize_params(self) -> None:
        wf = WorkspaceFolder.from_path("/foo/bar/baz")
        params = get_initialize_params(
            [wf], ClientConfig(name="test", binary_args=[""], languages=[], tcp_port=None, init_options=None))
        self.assertNotIn("initializationOptions", params)
        params = get_initialize_params(
            [wf], ClientConfig(name="test", binary_args=[""], languages=[], tcp_port=None, init_options={}))
        self.assertIn("initializationOptions", params)
        self.assertEqual(params["initializationOptions"], {})
        params = get_initialize_params(
            [wf], ClientConfig(name="test", binary_args=[""], languages=[], tcp_port=None, init_options={"foo": "bar"}))
        self.assertIn("initializationOptions", params)
        self.assertEqual(params["initializationOptions"], {"foo": "bar"})

    # @unittest.skip("need an example config")
    def test_can_create_session(self):
        config = ClientConfig(
            "test",
            ["cmd.exe"] if sublime.platform() == "windows" else ["ls"],
            None, [], [], None, [TEST_LANGUAGE])
        project_path = "/"
        folders = [WorkspaceFolder.from_path(project_path)]
        session = self.assert_if_none(
            create_session(config, folders, dict(), Settings()))
        session.client.transport.close()

    def test_can_get_started_session(self):
        post_initialize_callback = unittest.mock.Mock()
        session = self.make_session(
            MockClient(),
            on_post_initialize=post_initialize_callback)
        self.assertIsNotNone(session.client)
        self.assertTrue(session.has_capability("testing"))
        self.assertTrue(session.get_capability("testing"))
        assert post_initialize_callback.call_count == 1

    def test_pre_initialize_callback_is_invoked(self):
        pre_initialize_callback = unittest.mock.Mock()
        post_initialize_callback = unittest.mock.Mock()
        session = self.make_session(
            MockClient(),
            on_pre_initialize=pre_initialize_callback,
            on_post_initialize=post_initialize_callback)
        self.assertIsNotNone(session.client)
        self.assertTrue(session.has_capability("testing"))
        self.assertTrue(session.get_capability("testing"))
        assert pre_initialize_callback.call_count == 1
        assert post_initialize_callback.call_count == 1

    def test_can_shutdown_session(self):
        post_initialize_callback = unittest.mock.Mock()
        post_exit_callback = unittest.mock.Mock()
        session = self.make_session(
            MockClient(),
            on_post_initialize=post_initialize_callback,
            on_post_exit=post_exit_callback)
        self.assertIsNotNone(session.client)
        self.assertTrue(session.has_capability("testing"))
        assert post_initialize_callback.call_count == 1
        session.end()
        self.assertIsNone(session.client)
        self.assertFalse(session.has_capability("testing"))
        self.assertIsNone(session.get_capability("testing"))
        assert post_exit_callback.call_count == 1

    def test_document_sync_capabilities(self) -> None:
        client = MockClient()
        client.responses = {
            'initialize': {
                'capabilities': {
                    'textDocumentSync': {
                        "openClose": True,
                        "change": TextDocumentSyncKindFull,
                        "save": True}}}}  # A boolean with value true means "send didSave"
        session = Session(TEST_CONFIG, [], client)
        self.assertTrue(session.should_notify_did_open())
        self.assertTrue(session.should_notify_did_close())
        self.assertEqual(session.text_sync_kind(), TextDocumentSyncKindFull)
        self.assertTrue(session.should_notify_did_change())
        self.assertFalse(session.should_notify_will_save())
        self.assertEqual(session.should_notify_did_save(), (True, False))

        client.responses = {
            'initialize': {
                'capabilities': {
                    'textDocumentSync': {
                        "openClose": False,
                        "change": TextDocumentSyncKindNone,
                        "save": {},  # An empty dict means "send didSave"
                        "willSave": True,
                        "willSaveWaitUntil": False}}}}
        session = Session(TEST_CONFIG, [], client)
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

        client.responses = {
            'initialize': {
                'capabilities': {
                    'textDocumentSync': {
                        "openClose": False,
                        "change": TextDocumentSyncKindIncremental,
                        "save": {"includeText": True},
                        "willSave": False,
                        "willSaveWaitUntil": True}}}}
        session = Session(TEST_CONFIG, [], client)
        self.assertFalse(session.should_notify_did_open())
        self.assertFalse(session.should_notify_did_close())
        self.assertEqual(session.text_sync_kind(), TextDocumentSyncKindIncremental)
        self.assertTrue(session.should_notify_did_change())
        self.assertFalse(session.should_notify_will_save())
        self.assertEqual(session.should_notify_did_save(), (True, True))

        client.responses = {
            'initialize': {
                'capabilities': {  # backwards compatible :)
                    'textDocumentSync': TextDocumentSyncKindIncremental}}}
        session = Session(TEST_CONFIG, [], client)
        self.assertTrue(session.should_notify_did_open())
        self.assertTrue(session.should_notify_did_close())
        self.assertEqual(session.text_sync_kind(), TextDocumentSyncKindIncremental)
        self.assertTrue(session.should_notify_did_change())
        self.assertFalse(session.should_notify_will_save())  # old-style text sync will never send willSave
        self.assertEqual(session.should_notify_did_save(), (False, False))

        client.responses = {
            'initialize': {
                'capabilities': {  # backwards compatible :)
                    'textDocumentSync': TextDocumentSyncKindNone}}}
        session = Session(TEST_CONFIG, [], client)
        self.assertFalse(session.should_notify_did_open())
        self.assertFalse(session.should_notify_did_close())
        self.assertEqual(session.text_sync_kind(), TextDocumentSyncKindNone)
        self.assertFalse(session.should_notify_did_change())
        self.assertFalse(session.should_notify_will_save())
        self.assertEqual(session.should_notify_did_save(), (False, False))

        client.responses = {
            'initialize': {
                'capabilities': {
                    'textDocumentSync': {
                        "openClose": True,
                        "save": False,
                        "change": TextDocumentSyncKindIncremental}}}}
        session = Session(TEST_CONFIG, [], client)
        self.assertTrue(session.should_notify_did_open())
        self.assertTrue(session.should_notify_did_close())
        self.assertEqual(session.text_sync_kind(), TextDocumentSyncKindIncremental)
        self.assertTrue(session.should_notify_did_change())
        self.assertFalse(session.should_notify_will_save())
        self.assertEqual(session.should_notify_did_save(), (False, False))

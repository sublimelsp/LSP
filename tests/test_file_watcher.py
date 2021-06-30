from LSP.plugin import FileWatcher
from LSP.plugin import FileWatcherEvent
from LSP.plugin import FileWatcherKind
from LSP.plugin import FileWatcherProtocol
from LSP.plugin.core.file_watcher import file_watcher_kind_to_lsp_file_change_type
from LSP.plugin.core.file_watcher import register_file_watcher_implementation
from LSP.plugin.core.protocol import WatchKindChange, WatchKindCreate, WatchKindDelete
from LSP.plugin.core.types import ClientConfig
from LSP.plugin.core.typing import Generator, List
from os.path import join
from setup import expand
from setup import TextDocumentTestCase
import sublime


def setup_workspace_folder() -> str:
    window = sublime.active_window()
    folder_path = expand(join('$packages', 'LSP', 'tests'), window)
    window.set_project_data({
        'folders': [
            {
                'name': 'folder',
                'path': folder_path,
            }
        ]
    })
    return folder_path


class TestFileWatcher(FileWatcher):

    # The list of watchers created by active sessions.
    _active_watchers = []  # type: List[TestFileWatcher]

    @classmethod
    def create(
        cls,
        root_path: str,
        glob: str,
        kind: List[FileWatcherKind],
        ignores: List[str],
        handler: FileWatcherProtocol
    ) -> 'TestFileWatcher':
        watcher = TestFileWatcher(root_path, glob, kind, ignores, handler)
        cls._active_watchers.append(watcher)
        return watcher

    def __init__(
        self,
        root_path: str,
        glob: str,
        kind: List[FileWatcherKind],
        ignores: List[str],
        handler: FileWatcherProtocol
    ) -> None:
        self.root_path = root_path
        self.glob = glob
        self.kind = kind
        self.ignores = ignores
        self.handler = handler

    def destroy(self) -> None:
        self.handler = None
        self._active_watchers.remove(self)

    def trigger_event(self, events: List[FileWatcherEvent]) -> None:

        def trigger_async():
            if self.handler:
                self.handler.on_file_event_async(events)

        sublime.set_timeout_async(trigger_async)


class FileWatcherDocumentTestCase(TextDocumentTestCase):
    """
    Changes TextDocumentTestCase behavior so that the initialization and destroy of the config
    and the view happens before and after every test rather than per-testsuite.
    """

    @classmethod
    def setUpClass(cls) -> None:
        # Don't call the superclass.
        register_file_watcher_implementation(TestFileWatcher)

    @classmethod
    def tearDownClass(cls) -> None:
        # Don't call the superclass.
        pass

    def setUp(self) -> Generator:
        self.assertEqual(len(TestFileWatcher._active_watchers), 0)
        # Watchers are only registered when there are workspace folders so add a folder.
        self.folder_root_path = setup_workspace_folder()
        yield from super().setUpClass()
        yield from super().setUp()

    def tearDown(self) -> Generator:
        yield from super().tearDownClass()
        self.assertEqual(len(TestFileWatcher._active_watchers), 0)
        # Restore original project data.
        window = sublime.active_window()
        window.set_project_data(None)


class FileWatcherStaticTests(FileWatcherDocumentTestCase):

    @classmethod
    def get_stdio_test_config(cls) -> ClientConfig:
        return ClientConfig.from_config(
            super().get_stdio_test_config(),
            {
                'file_watcher': {
                    'glob': '*.js',
                    'kind': ['change'],
                    'ignores': ['.git'],
                }
            }
        )

    def test_initialize_params_includes_capability(self) -> None:
        self.assertIn('didChangeWatchedFiles', self.initialize_params['capabilities']['textDocument'])

    def test_creates_a_static_watcher(self) -> None:
        # Starting a session should have created a watcher.
        self.assertEqual(len(TestFileWatcher._active_watchers), 1)
        watcher = TestFileWatcher._active_watchers[0]
        self.assertEqual(watcher.glob, '*.js')
        self.assertEqual(watcher.kind, ['change'])
        self.assertEqual(watcher.ignores, ['.git'])
        self.assertEqual(watcher.root_path, self.folder_root_path)

    def test_handles_file_event(self) -> Generator:
        watcher = TestFileWatcher._active_watchers[0]
        filepath = join(self.folder_root_path, 'file.js')
        watcher.trigger_event([('change', filepath)])
        sent_notification = yield from self.await_message('workspace/didChangeWatchedFiles')
        self.assertIs(type(sent_notification['changes']), list)
        self.assertEqual(len(sent_notification['changes']), 1)
        change = sent_notification['changes'][0]
        self.assertEqual(change['type'], file_watcher_kind_to_lsp_file_change_type('change'))
        self.assertTrue(change['uri'].endswith('file.js'))


class FileWatcherDynamicTests(FileWatcherDocumentTestCase):

    def test_handles_dynamic_watcher_registration(self) -> Generator:
        registration_params = {
            'registrations': [
                {
                    'id': '111',
                    'method': 'workspace/didChangeWatchedFiles',
                    'registerOptions': {
                        'watchers': [
                            {
                                'globPattern': '*.py',
                                'kind': WatchKindCreate | WatchKindChange | WatchKindDelete,
                            }
                        ]
                    }
                }
            ]
        }
        yield self.make_server_do_fake_request('client/registerCapability', registration_params)
        self.assertEqual(len(TestFileWatcher._active_watchers), 1)
        watcher = TestFileWatcher._active_watchers[0]
        self.assertEqual(watcher.glob, '*.py')
        self.assertEqual(watcher.kind, ['create', 'change', 'delete'])
        self.assertEqual(watcher.root_path, self.folder_root_path)
        # Trigger the file event
        filepath = join(self.folder_root_path, 'file.py')
        watcher.trigger_event([('create', filepath), ('change', filepath)])
        sent_notification = yield from self.await_message('workspace/didChangeWatchedFiles')
        self.assertIs(type(sent_notification['changes']), list)
        self.assertEqual(len(sent_notification['changes']), 2)
        change1 = sent_notification['changes'][0]
        self.assertEqual(change1['type'], file_watcher_kind_to_lsp_file_change_type('create'))
        self.assertTrue(change1['uri'].endswith('file.py'))
        change2 = sent_notification['changes'][1]
        self.assertEqual(change2['type'], file_watcher_kind_to_lsp_file_change_type('change'))
        self.assertTrue(change2['uri'].endswith('file.py'))

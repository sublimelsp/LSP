from LSP.plugin import FileWatcher
from LSP.plugin import FileWatcherEvent
from LSP.plugin import FileWatcherKind
from LSP.plugin import FileWatcherProtocol
from LSP.plugin.core.file_watcher import file_watcher_kind_to_lsp_file_change_type
from LSP.plugin.core.file_watcher import register_file_watcher_implementation
from LSP.plugin.core.protocol import WatchKindCreate
from LSP.plugin.core.types import ClientConfig
from LSP.plugin.core.typing import Generator, List
from LSP.plugin.core.url import uri_to_filename
from os.path import join
from setup import expand
from setup import TextDocumentTestCase
import sublime


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


class FileWatcherStaticTests(TextDocumentTestCase):

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

    @classmethod
    def setUpClass(cls) -> Generator:
        # Watchers are only registered when there are workspace folders so add a folder.
        window = sublime.active_window()
        cls.original_project_data = window.project_data()
        cls.folder_root_path = expand(join('$packages', 'LSP', 'tests'), window)
        window.set_project_data({
            'folders': [
                {
                    'name': 'folder',
                    'path': cls.folder_root_path,
                }
            ]
        })
        register_file_watcher_implementation(TestFileWatcher)
        yield from super().setUpClass()

    @classmethod
    def tearDownClass(cls) -> Generator:
        yield from super().tearDownClass()
        # Restore original project data.
        window = sublime.active_window()
        window.set_project_data(cls.original_project_data)
        cls.original_project_data = None

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
        self.assertEqual(uri_to_filename(change['uri']), filepath)


class FileWatcherDynamicTests(TextDocumentTestCase):

    @classmethod
    def setUpClass(cls) -> Generator:
        # Watchers are only registered when there are workspace folders so add a folder.
        window = sublime.active_window()
        cls.original_project_data = window.project_data()
        cls.folder_root_path = expand(join('$packages', 'LSP', 'tests'), window)
        window.set_project_data({
            'folders': [
                {
                    'name': 'folder',
                    'path': cls.folder_root_path,
                }
            ]
        })
        register_file_watcher_implementation(TestFileWatcher)
        yield from super().setUpClass()

    @classmethod
    def tearDownClass(cls) -> Generator:
        yield from super().tearDownClass()
        # Restore original project data.
        window = sublime.active_window()
        window.set_project_data(cls.original_project_data)
        cls.original_project_data = None

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
                                'kind': WatchKindCreate,
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
        self.assertEqual(watcher.kind, ['create'])
        self.assertEqual(watcher.root_path, self.folder_root_path)

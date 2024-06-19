from __future__ import annotations
from LSP.plugin import FileWatcher
from LSP.plugin import FileWatcherEvent
from LSP.plugin import FileWatcherEventType
from LSP.plugin import FileWatcherProtocol
from LSP.plugin.core.file_watcher import file_watcher_event_type_to_lsp_file_change_type
from LSP.plugin.core.file_watcher import register_file_watcher_implementation
from LSP.plugin.core.protocol import WatchKind
from LSP.plugin.core.types import ClientConfig
from LSP.plugin.core.types import sublime_pattern_to_glob
from os.path import join
from setup import expand
from setup import TextDocumentTestCase
from typing import Generator, List, Optional
import sublime
import unittest


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
    _active_watchers: List[TestFileWatcher] = []

    @classmethod
    def create(
        cls,
        root_path: str,
        patterns: List[str],
        events: List[FileWatcherEventType],
        ignores: List[str],
        handler: FileWatcherProtocol
    ) -> TestFileWatcher:
        watcher = TestFileWatcher(root_path, patterns, events, ignores, handler)
        cls._active_watchers.append(watcher)
        return watcher

    def __init__(
        self,
        root_path: str,
        patterns: List[str],
        events: List[FileWatcherEventType],
        ignores: List[str],
        handler: FileWatcherProtocol
    ) -> None:
        self.root_path = root_path
        self.patterns = patterns
        self.events = events
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
        window.set_project_data({})


class FileWatcherStaticTests(FileWatcherDocumentTestCase):

    @classmethod
    def get_stdio_test_config(cls) -> ClientConfig:
        return ClientConfig.from_config(
            super().get_stdio_test_config(),
            {
                'file_watcher': {
                    'patterns': ['*.js'],
                    'events': ['change'],
                    'ignores': ['.git'],
                }
            }
        )

    def test_initialize_params_includes_capability(self) -> None:
        self.assertIn('didChangeWatchedFiles', self.initialize_params['capabilities']['workspace'])

    def test_creates_static_watcher(self) -> None:
        # Starting a session should have created a watcher.
        self.assertEqual(len(TestFileWatcher._active_watchers), 1)
        watcher = TestFileWatcher._active_watchers[0]
        self.assertEqual(watcher.patterns, ['*.js'])
        self.assertEqual(watcher.events, ['change'])
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
        self.assertEqual(change['type'], file_watcher_event_type_to_lsp_file_change_type('change'))
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
                                'kind': WatchKind.Create | WatchKind.Change | WatchKind.Delete,
                            }
                        ]
                    }
                }
            ]
        }
        yield self.make_server_do_fake_request('client/registerCapability', registration_params)
        self.assertEqual(len(TestFileWatcher._active_watchers), 1)
        watcher = TestFileWatcher._active_watchers[0]
        self.assertEqual(watcher.patterns, ['*.py'])
        self.assertEqual(watcher.events, ['create', 'change', 'delete'])
        self.assertEqual(watcher.root_path, self.folder_root_path)
        # Trigger the file event
        filepath = join(self.folder_root_path, 'file.py')
        watcher.trigger_event([('create', filepath), ('change', filepath)])
        sent_notification = yield from self.await_message('workspace/didChangeWatchedFiles')
        self.assertIs(type(sent_notification['changes']), list)
        self.assertEqual(len(sent_notification['changes']), 2)
        change1 = sent_notification['changes'][0]
        self.assertEqual(change1['type'], file_watcher_event_type_to_lsp_file_change_type('create'))
        self.assertTrue(change1['uri'].endswith('file.py'))
        change2 = sent_notification['changes'][1]
        self.assertEqual(change2['type'], file_watcher_event_type_to_lsp_file_change_type('change'))
        self.assertTrue(change2['uri'].endswith('file.py'))


class PatternToGlobTests(unittest.TestCase):

    def test_basic_directory_patterns(self):
        patterns = [
            '.git',
            'CVS',
            '.Trash-*',
        ]
        self._verify_patterns(
            patterns,
            [
                '**/.git/**',
                '**/CVS/**',
                '**/.Trash-*/**',
            ],
            is_directory_pattern=True)

    def test_complex_directory_patterns(self):
        patterns = [
            '*/foo',
            'foo/bar',
            'foo/bar/',
            '/foo',
        ]
        self._verify_patterns(
            patterns,
            [
                '**/foo/**',
                '**/foo/bar/**',
                '**/foo/bar/**',
                '/foo/**',
            ],
            is_directory_pattern=True)

    def test_basic_file_patterns(self):
        self._verify_patterns(
            [
                '*.pyc',
                ".DS_Store",

            ],
            [
                '**/*.pyc',
                '**/.DS_Store',
            ],
            is_directory_pattern=False)

    def test_complex_file_patterns(self):
        self._verify_patterns(
            [
                "/*.pyo",
            ],
            [
                '/*.pyo',
            ],
            is_directory_pattern=False)

    def test_project_relative_patterns(self):
        self._verify_patterns(['//foo'], ['/Users/me/foo/**'], is_directory_pattern=True, root_path='/Users/me')
        self._verify_patterns(['//*.pyo'], ['/Users/me/*.pyo'], is_directory_pattern=False, root_path='/Users/me')
        # Without root_path those will be treated as absolute paths even when starting with multiple slashes.
        self._verify_patterns(['//foo'], ['//foo/**'], is_directory_pattern=True)
        self._verify_patterns(['//*.pyo'], ['//*.pyo'], is_directory_pattern=False)

    def _verify_patterns(
        self,
        patterns: List[str],
        expected: List[str],
        is_directory_pattern: bool,
        root_path: Optional[str] = None
    ) -> None:
        glob_patterns = [
            sublime_pattern_to_glob(pattern, is_directory_pattern=is_directory_pattern, root_path=root_path)
            for pattern in patterns
        ]
        self.assertEqual(glob_patterns, expected)

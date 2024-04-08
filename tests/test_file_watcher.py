from LSP.plugin import FileWatcher
from LSP.plugin import FileWatcherEvent
from LSP.plugin import FileWatcherEventType
from LSP.plugin import FileWatcherProtocol
from LSP.plugin.core.file_watcher import file_watcher_event_type_to_lsp_file_change_type
from LSP.plugin.core.file_watcher import register_file_watcher_implementation
from LSP.plugin.core.protocol import WatchKind
from LSP.plugin.core.types import ClientConfig
from LSP.plugin.core.types import sublime_pattern_to_glob
from LSP.plugin.core.typing import Generator, List, Optional
from os.path import join
from setup import expand
from setup import TextDocumentTestCase
import sublime
import unittest


class TestFileWatcher(FileWatcher):

    # The list of watchers created by active sessions.
    _active_watchers = []  # type: List[TestFileWatcher]

    @classmethod
    def create(
        cls,
        root_path: str,
        patterns: List[str],
        events: List[FileWatcherEventType],
        ignores: List[str],
        handler: FileWatcherProtocol
    ) -> 'TestFileWatcher':
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

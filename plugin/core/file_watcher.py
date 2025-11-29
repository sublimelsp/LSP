from __future__ import annotations
from ...protocol import FileChangeType
from ...protocol import WatchKind
from abc import ABCMeta
from abc import abstractmethod
from typing import Literal, Protocol, Tuple, Union

DEFAULT_WATCH_KIND = WatchKind.Create | WatchKind.Change | WatchKind.Delete

FileWatcherEventType = Union[Literal['create'], Literal['change'], Literal['delete']]
FilePath = str
FileWatcherEvent = Tuple[FileWatcherEventType, FilePath]


def lsp_watch_kind_to_file_watcher_event_types(kind: WatchKind) -> list[FileWatcherEventType]:
    event_types: list[FileWatcherEventType] = []
    if kind & WatchKind.Create:
        event_types.append('create')
    if kind & WatchKind.Change:
        event_types.append('change')
    if kind & WatchKind.Delete:
        event_types.append('delete')
    return event_types


def file_watcher_event_type_to_lsp_file_change_type(kind: FileWatcherEventType) -> FileChangeType:
    return {
        'create': FileChangeType.Created,
        'change': FileChangeType.Changed,
        'delete': FileChangeType.Deleted,
    }[kind]


class FileWatcherProtocol(Protocol):
    def on_file_event_async(self, events: list[FileWatcherEvent]) -> None:
        """
        Called on file watcher events.
        This API must be triggered on async thread.

        :param events: The list of events to notify about.
        """
        ...


class FileWatcher(metaclass=ABCMeta):
    """
    A public interface of a file watcher implementation.

    The interface implements the file watcher and notifies the `handler` (through the `on_file_event_async` method)
    on file event changes.
    """

    @classmethod
    @abstractmethod
    def create(
        cls,
        root_path: str,
        patterns: list[str],
        events: list[FileWatcherEventType],
        ignores: list[str],
        handler: FileWatcherProtocol
    ) -> FileWatcher:
        """
        Creates a new instance of the file watcher.

        :param patterns: The list of glob pattern to enable watching for.
        :param events: The type of events that should be watched.
        :param ignores: The list of glob patterns that should excluded from file watching.

        :returns: A new instance of file watcher.
        """
        pass

    @abstractmethod
    def destroy(self) -> None:
        """
        Called before the file watcher is disabled.
        """
        pass


watcher_implementation: type[FileWatcher] | None = None


def register_file_watcher_implementation(file_watcher: type[FileWatcher]) -> None:
    global watcher_implementation
    if watcher_implementation:
        print('LSP: Watcher implementation already registered. Overwriting.')
    watcher_implementation = file_watcher


def get_file_watcher_implementation() -> type[FileWatcher] | None:
    return watcher_implementation

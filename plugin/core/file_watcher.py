from .typing import List, Optional, Protocol, Tuple, Type
from abc import ABCMeta
from abc import abstractmethod


DEFAULT_IGNORES = ['**/.git/**', '**/node_modules/**', '**/.hg/**']

WatchKind = int
FilePath = str
FileEvent = Tuple[WatchKind, FilePath]


class WatchKindValue:
    CREATE = 1
    CHANGE = 2
    DELETE = 4


WATCHER_TYPE_TO_KIND = {
    'create': WatchKindValue.CREATE,
    'change': WatchKindValue.CHANGE,
    'delete': WatchKindValue.DELETE,
}


class FileWatcherProtocol(Protocol):
    def on_file_event(self, events: List[FileEvent]) -> None:
        ...


class FileWatcher(metaclass=ABCMeta):
    """
    A public interface of a file watcher implementation.
    """

    @classmethod
    @abstractmethod
    def create(
        cls,
        root_path: str,
        glob: str,
        kind: WatchKind,
        ignores: List[str],
        handler: FileWatcherProtocol
    ) -> 'FileWatcher':
        """
        Creates a new instance of the file watcher.

        :param glob: The glob pattern to enable watching for.
        :param kind: The kind of events that should be watched.
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


watcher_implementation = None  # type: Optional[Type[FileWatcher]]


def register_file_watcher_implementation(file_watcher: Type[FileWatcher]) -> None:
    global watcher_implementation
    if watcher_implementation:
        print('LSP: Watcher implementation already registered. Overwriting.')
    watcher_implementation = file_watcher


def get_file_watcher_implementation() -> Optional[Type[FileWatcher]]:
    return watcher_implementation

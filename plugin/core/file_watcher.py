from .protocol import FileChangeType, FileChangeTypeCreated, FileChangeTypeChanged, FileChangeTypeDeleted
from .protocol import WatchKind, WatchKindCreate, WatchKindChange, WatchKindDelete
from .typing import List, Literal, Optional, Protocol, Tuple, Type, Union
from abc import ABCMeta
from abc import abstractmethod

DEFAULT_IGNORES = ['**/.git/**', '**/node_modules/**', '**/.hg/**']
DEFAULT_KIND = WatchKindCreate | WatchKindChange | WatchKindDelete

FileWatcherKind = Union[Literal['create'], Literal['change'], Literal['delete']]
FilePath = str
FileWatcherEvent = Tuple[FileWatcherKind, FilePath]


def lsp_watch_kind_to_file_watcher_kind(kind: WatchKind) -> List[FileWatcherKind]:
    kinds = []  # type: List[FileWatcherKind]
    if kind & WatchKindCreate:
        kinds.append('create')
    if kind & WatchKindChange:
        kinds.append('change')
    if kind & WatchKindDelete:
        kinds.append('delete')
    return kinds


def file_watcher_kind_to_lsp_file_change_type(kind: FileWatcherKind) -> FileChangeType:
    return {
        'create': FileChangeTypeCreated,
        'change': FileChangeTypeChanged,
        'delete': FileChangeTypeDeleted,
    }[kind]


class FileWatcherProtocol(Protocol):
    def on_file_event(self, events: List[FileWatcherEvent]) -> None:
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
        kind: List[FileWatcherKind],
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

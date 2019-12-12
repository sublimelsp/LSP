from .logging import debug
from .protocol import WorkspaceFolder
from .types import WindowLike
import os

try:
    from typing import List, Optional, Any, Dict, Iterable, Union, Callable
    assert List and Optional and Any and Dict and Iterable and Union and Callable
except ImportError:
    pass


class Workspace(object):

    def __init__(self, folders: 'List[str]') -> None:
        self.folders = folders
        self._workspace_folders = [WorkspaceFolder.from_path(f) for f in self.folders]

    def is_empty(self) -> bool:
        return not any(self.folders)

    @property
    def workspace_folders(self) -> 'List[WorkspaceFolder]':
        return self._workspace_folders

    @property
    def working_directory(self) -> 'Optional[str]':
        return self.folders[0] if self.folders else None

    def __eq__(self, other: object) -> bool:
        if isinstance(other, Workspace):
            return self.folders == other.folders
        else:
            raise NotImplementedError()


class WorkspaceManager(object):

    def __init__(self, window: WindowLike, on_changed: 'Callable[[Workspace], None]',
                 on_switched: 'Callable[[Workspace], None]') -> None:
        self._window = window
        self._on_changed = on_changed
        self._on_switched = on_switched
        self._workspace = get_workspace(self._window, None)
        self._current_project_file_name = self._window.project_file_name()

    @property
    def current(self) -> 'Workspace':
        return self._workspace

    def update(self, file_path: str) -> None:
        new_workspace = get_workspace(self._window, file_path)
        if new_workspace != self._workspace:
            if self._can_update_to(new_workspace):
                self._workspace = new_workspace
                self._on_changed(new_workspace)
            else:
                self._workspace = new_workspace
                self._on_switched(new_workspace)

    def _can_update_to(self, workspace: Workspace) -> bool:
        if self._workspace.is_empty():
            return True

        if self._current_project_file_name and self._window.project_file_name() == self._current_project_file_name:
            return True

        for folder in self._workspace.folders:
            if folder in workspace.folders:
                return True

        return False


def get_workspace(window: WindowLike, file_path: 'Optional[str]' = None) -> Workspace:
    folders = window.folders()
    if file_path:
        sorted_folders = []  # type: List[str]
        if folders:
            for folder in folders:
                if file_path and file_path.startswith(folder):
                    sorted_folders.insert(0, folder)
                else:
                    sorted_folders.append(folder)
        else:
            sorted_folders = [os.path.dirname(file_path)]

        return Workspace(sorted_folders)
    else:
        return Workspace(folders)


def get_workspace_folders(window: WindowLike, file_path: 'Optional[str]' = None) -> 'List[WorkspaceFolder]':
    folders = window.folders()
    sorted_folders = []  # type: List[str]
    if folders:
        for folder in folders:
            if file_path and file_path.startswith(folder):
                sorted_folders.insert(0, folder)
            else:
                sorted_folders.append(folder)
    elif file_path:
        sorted_folders.append(os.path.dirname(file_path))

    return [WorkspaceFolder.from_path(folder) for folder in sorted_folders]


def enable_in_project(window: 'Any', config_name: str) -> None:
    project_data = window.project_data()
    if isinstance(project_data, dict):
        project_settings = project_data.setdefault('settings', dict())
        project_lsp_settings = project_settings.setdefault('LSP', dict())
        project_client_settings = project_lsp_settings.setdefault(config_name, dict())
        project_client_settings['enabled'] = True
        window.set_project_data(project_data)
    else:
        debug('non-dict returned in project_settings: ', project_data)


def disable_in_project(window: 'Any', config_name: str) -> None:
    project_data = window.project_data()
    if isinstance(project_data, dict):
        project_settings = project_data.setdefault('settings', dict())
        project_lsp_settings = project_settings.setdefault('LSP', dict())
        project_client_settings = project_lsp_settings.setdefault(config_name, dict())
        project_client_settings['enabled'] = False
        window.set_project_data(project_data)
    else:
        debug('non-dict returned in project_settings: ', project_data)


def get_project_config(window: 'Any') -> dict:
    project_data = window.project_data() or dict()
    if isinstance(project_data, dict):
        project_settings = project_data.setdefault('settings', dict())
        project_lsp_settings = project_settings.setdefault('LSP', dict())
        return project_lsp_settings
    else:
        debug('non-dict returned in project_settings: ', project_data)
        return dict()

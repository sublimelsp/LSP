from .logging import debug
from .protocol import WorkspaceFolder
from .types import WindowLike

try:
    from typing import List, Optional, Any, Dict, Iterable, Union, Callable
    assert List and Optional and Any and Dict and Iterable and Union and Callable
except ImportError:
    pass


class ProjectFolders(object):

    def __init__(self, window: WindowLike, on_changed: 'Callable[[List[str]], None]',
                 on_switched: 'Callable[[List[str]], None]') -> None:
        self._window = window
        self._on_changed = on_changed
        self._on_switched = on_switched
        self._current_project_file_name = self._window.project_file_name()
        self._set_folders(window.folders())

    def update(self) -> None:
        new_folders = self._window.folders()
        if set(new_folders) != set(self.folders):
            is_update = self._can_update_to(new_folders)
            self._set_folders(new_folders)
            if is_update:
                self._on_changed(new_folders)
            else:
                self._on_switched(new_folders)

    def _set_folders(self, folders: 'List[str]') -> None:
        self.folders = folders

    def _can_update_to(self, new_folders: 'List[str]') -> bool:
        """ Should detect difference between a project switch and a change to folders in the loaded project """
        if not self.folders:
            return True

        if self._current_project_file_name and self._window.project_file_name() == self._current_project_file_name:
            return True

        for folder in self.folders:
            if folder in new_folders:
                return True

        return False


def get_workspace_folders(folders: 'List[str]') -> 'List[WorkspaceFolder]':
    return [WorkspaceFolder.from_path(f) for f in folders]


def sorted_workspace_folders(folders: 'List[str]', file_path: str) -> 'List[WorkspaceFolder]':
    sorted_folders = []  # type: List[WorkspaceFolder]
    for folder in folders:
        if file_path and file_path.startswith(folder):
            sorted_folders.insert(0, WorkspaceFolder.from_path(folder))
        else:
            sorted_folders.append(WorkspaceFolder.from_path(folder))
    return sorted_folders


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

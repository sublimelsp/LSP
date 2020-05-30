from .logging import debug
from .protocol import WorkspaceFolder
from .types import WindowLike
from .typing import List, Any


def is_subpath_of(file_path: str, potential_subpath: str) -> bool:
    """ Case insensitive, file paths are not normalized when converted from uri"""
    return file_path.lower().startswith(potential_subpath.lower())


class ProjectFolders(object):

    def __init__(self, window: WindowLike) -> None:
        self._window = window
        self.folders = self._window.folders()  # type: List[str]

    def update(self) -> List[WorkspaceFolder]:
        self.folders = self._window.folders()
        return get_workspace_folders(self.folders)

    def includes_path(self, file_path: str) -> bool:
        if self.folders:
            return any(is_subpath_of(file_path, folder) for folder in self.folders)
        else:
            return True


def get_workspace_folders(folders: List[str]) -> List[WorkspaceFolder]:
    return [WorkspaceFolder.from_path(f) for f in folders]


def sorted_workspace_folders(folders: List[str], file_path: str) -> List[WorkspaceFolder]:
    matching_paths = []  # type: List[str]
    other_paths = []  # type: List[str]

    for folder in folders:
        is_subpath = is_subpath_of(file_path, folder)
        if is_subpath:
            if matching_paths and len(folder) > len(matching_paths[0]):
                matching_paths.insert(0, folder)
            else:
                matching_paths.append(folder)
        else:
            other_paths.append(folder)

    return [WorkspaceFolder.from_path(path) for path in matching_paths + other_paths]


def enable_in_project(window: Any, config_name: str) -> None:
    project_data = window.project_data()
    if isinstance(project_data, dict):
        project_settings = project_data.setdefault('settings', dict())
        project_lsp_settings = project_settings.setdefault('LSP', dict())
        project_client_settings = project_lsp_settings.setdefault(config_name, dict())
        project_client_settings['enabled'] = True
        window.set_project_data(project_data)
    else:
        debug('non-dict returned in project_settings: ', project_data)


def disable_in_project(window: Any, config_name: str) -> None:
    project_data = window.project_data()
    if isinstance(project_data, dict):
        project_settings = project_data.setdefault('settings', dict())
        project_lsp_settings = project_settings.setdefault('LSP', dict())
        project_client_settings = project_lsp_settings.setdefault(config_name, dict())
        project_client_settings['enabled'] = False
        window.set_project_data(project_data)
    else:
        debug('non-dict returned in project_settings: ', project_data)

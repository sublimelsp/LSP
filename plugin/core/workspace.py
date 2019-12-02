from .logging import debug
from .protocol import WorkspaceFolder
from .types import WindowLike
import os

try:
    from typing import List, Optional, Any, Dict, Iterable, Union
    assert List and Optional and Any and Dict and Iterable and Union
except ImportError:
    pass


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

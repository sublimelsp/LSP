from .logging import debug
from .protocol import WorkspaceFolder
from .types import ViewLike
from .types import WindowLike
import os

try:
    from typing import List, Optional, Any, Dict, Iterable, Union
    assert List and Optional and Any and Dict and Iterable and Union
except ImportError:
    pass


def maybe_get_first_workspace_from_window(window: WindowLike) -> 'Optional[WorkspaceFolder]':
    folders = window.folders()
    if not folders:
        return None
    return WorkspaceFolder.from_path(folders[0])


def maybe_get_workspace_from_view(view_or_window: 'Any') -> 'Optional[WorkspaceFolder]':
    if hasattr(view_or_window, 'file_name'):
        filename = view_or_window.file_name()
    elif hasattr(view_or_window, 'active_view'):
        view = view_or_window.active_view()
        if not view:
            return None
        filename = view.file_name()
    else:
        return None
    if filename and os.path.exists(filename):  # https://github.com/tomv564/LSP/issues/644
        path = os.path.dirname(filename)
        return WorkspaceFolder.from_path(path)
    debug("the current file isn't saved to disk.")
    return None


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

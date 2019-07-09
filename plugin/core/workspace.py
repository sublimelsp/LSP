import os
try:
    from typing import List, Optional, Any
    assert List and Optional and Any
except ImportError:
    pass

from .logging import debug
# from .types import WindowLike


def get_project_path(window: 'Any') -> 'Optional[str]':
    """
    Returns the first project folder or the parent folder of the active view
    """
    if len(window.folders()):
        return window.folders()[0]
    else:
        view = window.active_view()
        if view:
            filename = view.file_name()
            if filename:
                project_path = os.path.dirname(filename)
                debug("Couldn't determine project directory since no folders are open! Using",
                      project_path, "as a fallback.")
                return project_path
            else:
                debug("Couldn't determine project directory since no folders are open",
                      "and the current file isn't saved on the disk.")
                return None
        else:
            debug("No view is active in current window")
            return None  # https://github.com/tomv564/LSP/issues/219


def get_common_parent(paths: 'List[str]') -> str:
    """
    Get the common parent directory of multiple paths.

    Python 3.5+ includes os.path.commonpath which does this, however Sublime
    currently embeds Python 3.3.
    """
    return os.path.commonprefix([path + '/' for path in paths]).rstrip('/')


def is_in_workspace(window: 'Any', file_path: str) -> bool:
    workspace_path = get_project_path(window)
    if workspace_path is None:
        return False

    common_dir = get_common_parent([workspace_path, file_path])
    return workspace_path == common_dir


def set_enabled_in_project(window, config_name: str, enabled: bool) -> None:
    project_data = window.project_data()
    if isinstance(project_data, dict):
        project_settings = project_data.setdefault('settings', {})
        project_lsp_settings = project_settings.setdefault('LSP', {})
        project_client_settings = project_lsp_settings.setdefault(config_name, {})
        project_client_settings['enabled'] = enabled
        window.set_project_data(project_data)
    else:
        debug('non-dict returned in project_settings:', project_data)


def get_project_config(window: 'Any') -> dict:
    project_data = window.project_data() or {}
    if isinstance(project_data, dict):
        project_settings = project_data.setdefault('settings', {})
        project_lsp_settings = project_settings.setdefault('LSP', {})
        return project_lsp_settings
    else:
        debug('non-dict returned in project_settings: ', project_data)
        return {}

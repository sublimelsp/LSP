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
    Returns the first project folder
    """
    if len(window.folders()):
        folder_paths = window.folders()
        return folder_paths[0]
    return None


def get_active_view_path(window: 'Any') -> 'Optional[str]':
    """
    Returns the path containing the active view, if any.
    """
    debug("couldn't determine project directory since no folders are open!")
    view = window.active_view()
    if view:
        filename = view.file_name()
        if filename and os.path.exists(filename):  # https://github.com/tomv564/LSP/issues/644
            project_path = os.path.dirname(filename)
            debug("using", project_path, "as a fallback.")
            return project_path
        else:
            debug("no fallback path possible because the current file isn't saved to disk.")
            return None
    else:
        debug("no view is active in current window")
        return None  # https://github.com/tomv564/LSP/issues/219


def enable_in_project(window, config_name: str) -> None:
    project_data = window.project_data()
    if isinstance(project_data, dict):
        project_settings = project_data.setdefault('settings', dict())
        project_lsp_settings = project_settings.setdefault('LSP', dict())
        project_client_settings = project_lsp_settings.setdefault(config_name, dict())
        project_client_settings['enabled'] = True
        window.set_project_data(project_data)
    else:
        debug('non-dict returned in project_settings: ', project_data)


def disable_in_project(window, config_name: str) -> None:
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

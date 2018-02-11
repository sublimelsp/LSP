import os
import sublime
try:
    from typing import List, Optional
    assert List and Optional
except ImportError:
    pass

from .settings import log


def get_project_path(window: sublime.Window) -> 'Optional[str]':
    """
    Returns the common root of all open folders in the window
    """
    if len(window.folders()):
        folder_paths = window.folders()
        return folder_paths[0]
    else:
        view = window.active_view()
        if view:
            filename = view.file_name()
            if filename:
                project_path = os.path.dirname(filename)
                log(2, "Couldn't determine project directory since no folders are open!"
                    "Using %s as a fallback.", project_path)
                return project_path
            else:
                log(2, "Couldn't determine project directory since no folders are open "
                    "and the current file isn't saved on the disk.")
                return None
        else:
            log(2, "No view is active in current window")
            return None  # https://github.com/tomv564/LSP/issues/219


def get_common_parent(paths: 'List[str]') -> str:
    """
    Get the common parent directory of multiple paths.

    Python 3.5+ includes os.path.commonpath which does this, however Sublime
    currently embeds Python 3.3.
    """
    return os.path.commonprefix([path + '/' for path in paths]).rstrip('/')


def is_in_workspace(window: sublime.Window, file_path: str) -> bool:
    workspace_path = get_project_path(window)
    if workspace_path is None:
        return False

    common_dir = get_common_parent([workspace_path, file_path])
    return workspace_path == common_dir


def enable_in_project(window, config_name: str) -> None:
    project_data = window.project_data() or dict()
    project_settings = project_data.setdefault('settings', dict())
    project_lsp_settings = project_settings.setdefault('LSP', dict())
    project_client_settings = project_lsp_settings.setdefault(config_name, dict())
    project_client_settings['enabled'] = True
    window.set_project_data(project_data)


def disable_in_project(window, config_name: str) -> None:
    project_data = window.project_data() or dict()
    project_settings = project_data.setdefault('settings', dict())
    project_lsp_settings = project_settings.setdefault('LSP', dict())
    project_client_settings = project_lsp_settings.setdefault(config_name, dict())
    project_client_settings['enabled'] = False
    window.set_project_data(project_data)


def get_project_config(window: sublime.Window) -> dict:
    project_data = window.project_data() or dict()
    project_settings = project_data.setdefault('settings', dict())
    project_lsp_settings = project_settings.setdefault('LSP', dict())
    return project_lsp_settings

import os
try:
    from typing import List, Optional, Any, Iterable
    assert List and Optional and Any and Iterable
except ImportError:
    pass

from .logging import debug
from .types import ViewLike


def get_filename_from_view(view: ViewLike) -> 'Optional[str]':
    if not view:
        debug("No view is active in current window")
        return None  # https://github.com/tomv564/LSP/issues/219
    filename = view.file_name()
    if not filename:
        debug("Couldn't determine project directory since no folders are open",
              "and the current file isn't saved on the disk.")
    return filename


def get_directory_name(view: ViewLike) -> 'Optional[str]':
    filename = get_filename_from_view(view)
    if filename:
        project_path = os.path.dirname(filename)
        return project_path
    return None


def find_path_among_multi_folders(folders: 'Iterable[str]',
                                  view: ViewLike) -> 'Optional[str]':
    filename = get_filename_from_view(view)
    if not filename:
        return None
    folders = [os.path.realpath(f) for f in folders]
    file = view.file_name()
    if not file:
        return None
    file = os.path.realpath(file)
    while file not in folders:
        file = os.path.dirname(file)
        if os.path.dirname(file) == file:
            # We're at the root of the filesystem.
            file = None
            break
    debug('project path is', file)
    return file


def get_project_path(window: 'Any') -> 'Optional[str]':
    """
    Returns the project folder or the parent folder of the active view
    """
    if not window:
        return None
    num_folders = len(window.folders())
    if num_folders == 0:
        return get_directory_name(window.active_view())
    elif num_folders == 1:
        folder_paths = window.folders()
        return folder_paths[0]
    else:  # num_folders > 1
        return find_path_among_multi_folders(
            window.folders(),
            window.active_view())


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

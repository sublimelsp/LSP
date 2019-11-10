import os
from .logging import debug
from .url import filename_to_uri, uri_to_filename


try:
    from .types import ViewLike, WindowLike
    from typing import List, Optional, Any, Dict, Iterable
    assert List and Optional and Any and ViewLike and WindowLike and Dict and Iterable
except ImportError:
    pass


def ensure_absolute_path(project_base_path: str, folder: str) -> str:
    if os.path.isabs(folder):
        return folder
    else:
        return os.path.abspath(os.path.join(project_base_path, folder))


def absolute_project_base_path(window: 'WindowLike') -> str:
    project_file_name = window.project_file_name()
    if not project_file_name:
        return ""
    return os.path.dirname(os.path.abspath(project_file_name))


class Workspace:

    __slots__ = ('name', 'uri')

    def __init__(self, name: str, uri: str) -> None:
        self.name = name
        self.uri = uri

    @classmethod
    def from_sublime_project_data(cls, project_base_path: str, folder: 'Dict[str, Any]') -> 'Workspace':
        name = folder.get("name")  # type: Optional[str]
        path = folder.get("path")  # type: Optional[str]
        if not path:
            raise KeyError('"path" should be present in Sublime Text folder project data')
        path = ensure_absolute_path(project_base_path, path)
        if not os.path.isdir(path):
            raise ValueError("{} is not a directory".format(path))
        if not name:
            name = os.path.basename(path)
        return cls(name, filename_to_uri(path))

    def __repr__(self) -> str:
        return "{}('{}', '{}')".format(self.__class__.__name__, self.name, self.uri)

    def __str__(self) -> str:
        return self.uri

    def __eq__(self, other: 'Any') -> bool:
        if isinstance(other, Workspace):
            return self.name == other.name and self.uri == other.uri
        return False

    def to_dict(self) -> 'Dict[str, str]':
        return {"name": self.name, "uri": self.uri}


def get_project_data_or_throw(window: 'WindowLike') -> 'Dict[str, Any]':
    data = window.project_data()
    if data is None:
        raise AttributeError("window {} has no project data".format(window.id()))
    return data


def get_first_workspace_from_window(window: 'WindowLike') -> 'Workspace':
    data = get_project_data_or_throw(window)
    folder = data["folders"][0]
    path = folder.get("path")  # type: str
    project_file_name = window.project_file_name()
    if project_file_name:
        project_base_path = absolute_project_base_path(window)
        path = ensure_absolute_path(project_base_path, path)
    if not os.path.isdir(path):
        raise ValueError("{} is not a directory".format(path))
    return Workspace(name=os.path.basename(path), uri=filename_to_uri(path))


def get_workspaces_from_project_data(window: 'WindowLike') -> 'Optional[List[Workspace]]':
    data = get_project_data_or_throw(window)
    project_base_path = absolute_project_base_path(window)
    folders = data.get("folders")
    if folders is None:
        raise ValueError("window folders is None")
    return [Workspace.from_sublime_project_data(project_base_path, folder) for folder in folders]


def get_workspaces_from_window(window: 'WindowLike') -> 'Optional[List[Workspace]]':
    project_file_name = window.project_file_name()
    if project_file_name:
        return get_workspaces_from_project_data(window)
    try:
        return [get_first_workspace_from_window(window)]
    except AttributeError as error:
        debug(error)
    return None


def get_common_prefix_of_workspaces(workspaces: 'Optional[List[Workspace]]') -> 'Optional[str]':
    if workspaces is None:
        return None
    return get_common_parent(uri_to_filename(workspace.uri) for workspace in workspaces)


def get_common_prefix_of_workspaces_for_window(window: 'WindowLike') -> 'Optional[str]':
    return get_common_prefix_of_workspaces(get_workspaces_from_window(window))


def get_common_parent(paths: 'Iterable[str]') -> str:
    """
    Returns the path containing the active view, if any.
    """
    return os.path.commonprefix([path + '/' for path in paths]).rstrip('/')


def enable_in_project(window: 'WindowLike', config_name: str) -> None:
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


def get_project_config(window: 'WindowLike') -> dict:
    project_data = window.project_data() or dict()
    if isinstance(project_data, dict):
        project_settings = project_data.setdefault('settings', dict())
        project_lsp_settings = project_settings.setdefault('LSP', dict())
        return project_lsp_settings
    else:
        debug('non-dict returned in project_settings: ', project_data)
        return dict()

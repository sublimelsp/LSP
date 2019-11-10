from . import test_sublime as test_sublime
from .sessions import Session
from .types import ClientConfig
from .types import LanguageConfig
from .types import ViewLike
from .types import WindowLike
from .workspace import Workspace
import os

try:
    from typing import Callable, List, Optional, Set, Dict, Any, Tuple, Iterable
    assert Callable and List and Optional and Set and Session and Dict and Any and Tuple and Iterable
except ImportError:
    pass


class TestDocumentHandlerFactory(object):
    def for_window(self, window, configs):
        return MockDocuments()


class MockSublimeSettings(object):
    def __init__(self, values):
        self._values = values

    def get(self, key, default=None):
        return self._values.get(key, default)

    def set(self, key, value):
        self._values[key] = value


class MockView(ViewLike):
    def __init__(self, file_name):
        self._file_name = file_name
        self._window = None
        self._settings = MockSublimeSettings({"syntax": "Plain Text"})
        self._status = dict()  # type: Dict[str, str]
        self._text = "asdf"

    def id(self) -> int:
        return 0

    def assign_syntax(self, syntax: str) -> None:
        pass

    def file_name(self):
        return self._file_name

    def set_window(self, window):
        self._window = window

    def set_status(self, key, status):
        self._status[key] = status

    def window(self):
        return self._window

    def settings(self):
        return self._settings

    def substr(self, region):
        return self._text

    def size(self):
        return len(self._text)

    def sel(self):
        return [test_sublime.Region(1, 1)]

    def score_selector(self, region, scope: str) -> int:
        return 1

    def buffer_id(self):
        return 1


class MockHandlerDispatcher(object):
    def __init__(self, can_start: bool = True) -> None:
        self._can_start = can_start
        self._initialized = set()  # type: Set[str]

    def on_start(self, config_name: str, window) -> bool:
        return self._can_start

    def on_initialized(self, config_name: str, window, client):
        self._initialized.add(config_name)


class MockWindow(WindowLike):
    def __init__(self, files_in_groups: 'List[List[ViewLike]]' = [], project_file_name: 'Optional[str]' = None) -> None:
        self._files_in_groups = files_in_groups
        self._project_file_name = project_file_name
        self._is_valid = True
        self._default_view = MockView(None)
        self._project_data = None  # type: Optional[Dict[str, Any]]
        self.commands = []  # type: List[Tuple[str, Optional[Dict[str, Any]]]]

    def id(self):
        return 0

    def folders(self):
        if not self._project_data:
            return []
        folders = []
        for folder in self._project_data.get("folders", []):
            folders.append(folder["path"])
        return folders

    def set_folders(self, folders):
        if self._project_data is None:
            self._project_data = {}
        self._project_data["folders"] = [{"path": folder} for folder in folders]

    def num_groups(self):
        return len(self._files_in_groups)

    def active_group(self):
        return 0

    def project_file_name(self) -> 'Optional[str]':
        return self._project_file_name

    def project_data(self) -> 'Optional[dict]':
        return self._project_data

    def set_project_data(self, data: 'Optional[dict]'):
        self._project_data = data

    def active_view(self) -> 'Optional[ViewLike]':
        return self.active_view_in_group(0)

    def close(self):
        self._is_valid = False

    def is_valid(self):
        return self._is_valid

    def extract_variables(self):
        return {
            "project_path": os.path.dirname(__file__)
        }

    def active_view_in_group(self, group):
        if group < len(self._files_in_groups):
            files = self._files_in_groups[group]
            if len(files) > 0:
                return files[0]
            else:
                return self._default_view

    def add_view_in_group(self, group, view):
        self._files_in_groups[group].append(view)

    def status_message(self, msg: str) -> None:
        pass

    def views(self):
        views = []
        for views_in_group in self._files_in_groups:
            if len(views_in_group) < 1:
                views.append(self._default_view)
            else:
                for view in views_in_group:
                    views.append(view)
        return views

    def find_open_file(self, path: str) -> 'Optional[ViewLike]':
        pass

    def run_command(self, command_name: str, command_args: 'Optional[Dict[str, Any]]') -> None:
        self.commands.append((command_name, command_args))


class TestGlobalConfigs(object):
    def for_window(self, window):
        return MockConfigs()


class MockConfigs(object):
    def __init__(self):
        self.all = [test_config]

    def is_supported(self, view):
        return any(self.scope_configs(view))

    def scope_configs(self, view, point=None):
        if view.file_name() is None:
            return [None]
        else:
            return [test_config]

    def syntax_configs(self, view):
        if view.settings().get("syntax") == "Plain Text":
            return [test_config]
        else:
            return []

    def syntax_supported(self, view: ViewLike) -> bool:
        return view.settings().get("syntax") == "Plain Text"

    def syntax_config_languages(self, view: ViewLike) -> 'Dict[str, LanguageConfig]':
        if self.syntax_supported(view):
            return {
                "test": test_language
            }
        else:
            return {}

    def update(self, configs: 'List[ClientConfig]') -> None:
        pass

    def disable(self, config_name: str) -> None:
        pass


class MockDocuments(object):
    def __init__(self):
        self._documents = []  # type: List[str]
        self._sessions = {}  # type: Dict[str, Session]

    def add_session(self, session: 'Session') -> None:
        self._sessions[session.config.name] = session

    def remove_session(self, config_name: str) -> None:
        del self._sessions[config_name]

    def handle_view_opened(self, view: ViewLike):
        file_name = view.file_name()
        if file_name:
            self._documents.append(file_name)

    def reset(self):
        self._documents = []


test_language = LanguageConfig("test", ["source.test"], ["Plain Text"])
test_config = ClientConfig("test", [], None, languages=[test_language])
test_workspaces = [Workspace(name="test", uri="file:///")]

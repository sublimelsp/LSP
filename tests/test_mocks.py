import test_sublime
from LSP.plugin.core.logging import debug
from LSP.plugin.core.protocol import Notification
from LSP.plugin.core.protocol import Request
from LSP.plugin.core.types import ClientConfig
from LSP.plugin.core.types import LanguageConfig
from LSP.plugin.core.types import Settings
from LSP.plugin.core.types import ViewLike
import os

try:
    from typing import Dict, Set, List, Optional, Any, Tuple, Callable
    assert Dict and Set and List and Optional and Any and Tuple and Callable
    from .sessions import Session
    assert Session
except ImportError:
    pass


TEST_LANGUAGE = LanguageConfig("test", ["source.test"], ["Plain Text"])
TEST_CONFIG = ClientConfig("test", [], None, languages=[TEST_LANGUAGE])
DISABLED_CONFIG = ClientConfig("test", [], None, languages=[TEST_LANGUAGE], enabled=False)

basic_responses = {
    'initialize': {
        'capabilities': {
            'testing': True,
            'hoverProvider': True,
            'completionProvider': {
                'triggerCharacters': ['.'],
                'resolveProvider': False
            },
            'textDocumentSync': {
                "openClose": True,
                "change": 1,
                "save": True
            },
            'definitionProvider': True,
            'typeDefinitionProvider': True,
            'declarationProvider': True,
            'implementationProvider': True,
            'documentFormattingProvider': True
        }
    }
}


class MockSettings(Settings):

    def __init__(self):
        Settings.__init__(self)
        self.log_payloads = False
        self.show_view_status = True


class MockSublimeSettings(object):
    def __init__(self, values):
        self._values = values

    def get(self, key, default=None):
        return self._values.get(key, default)

    def set(self, key, value):
        self._values[key] = value


class MockView(object):
    def __init__(self, file_name):
        self._file_name = file_name
        self._window = None
        self._settings = MockSublimeSettings({"syntax": "Plain Text"})
        self._status = dict()  # type: Dict[str, str]
        self._text = "asdf"
        self.commands = []  # type: List[Tuple[str, Dict[str, Any]]]

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

    def run_command(self, command_name: str, command_args: 'Dict[str, Any]') -> None:
        self.commands.append((command_name, command_args))


class MockHandlerDispatcher(object):
    def __init__(self, can_start: bool = True) -> None:
        self._can_start = can_start
        self._initialized = set()  # type: Set[str]

    def on_start(self, config_name: str, window) -> bool:
        return self._can_start

    def on_initialized(self, config_name: str, window, client):
        self._initialized.add(config_name)


class MockWindow(object):
    def __init__(self, files_in_groups: 'List[List[ViewLike]]' = [], folders: 'List[str]' = []) -> None:
        self._files_in_groups = files_in_groups
        self._is_valid = True
        self._folders = folders
        self._default_view = MockView(None)
        self._project_data = None  # type: Optional[Dict[str, Any]]
        self._project_file_name = None  # type: Optional[str]
        self.commands = []  # type: List[Tuple[str, Dict[str, Any]]]

    def id(self):
        return 0

    def folders(self):
        return self._folders

    def set_folders(self, folders):
        self._folders = folders

    def num_groups(self):
        return len(self._files_in_groups)

    def active_group(self):
        return 0

    def project_data(self) -> 'Optional[dict]':
        return self._project_data

    def set_project_data(self, data: 'Optional[dict]'):
        self._project_data = data

    def project_file_name(self) -> 'Optional[str]':
        return self._project_file_name

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
        views = []  # type: List[ViewLike]
        for views_in_group in self._files_in_groups:
            if len(views_in_group) < 1:
                views.append(self._default_view)
            else:
                for view in views_in_group:
                    views.append(view)
        return views

    def find_open_file(self, path: str) -> 'Optional[ViewLike]':
        pass

    def run_command(self, command_name: str, command_args: 'Dict[str, Any]') -> None:
        self.commands.append((command_name, command_args))


class TestGlobalConfigs(object):
    def for_window(self, window):
        return MockConfigs()


class MockConfigs(object):
    def __init__(self):
        self.all = [TEST_CONFIG]

    def is_supported(self, view):
        return any(self.scope_configs(view))

    def scope_configs(self, view, point=None):
        if view.file_name() is None:
            return [None]
        else:
            return [TEST_CONFIG]

    def syntax_configs(self, view, include_disabled: bool = False):
        if view.settings().get("syntax") == "Plain Text":
            return [TEST_CONFIG]
        else:
            return []

    def syntax_supported(self, view: ViewLike) -> bool:
        return view.settings().get("syntax") == "Plain Text"

    def syntax_config_languages(self, view: ViewLike) -> 'Dict[str, LanguageConfig]':
        if self.syntax_supported(view):
            return {
                "test": TEST_LANGUAGE
            }
        else:
            return {}

    def update(self) -> None:
        pass

    def enable_config(self, config_name: str) -> None:
        pass

    def disable_config(self, config_name: str) -> None:
        pass

    def disable_temporarily(self, config_name: str) -> None:
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

    def purge_changes(self, view: ViewLike) -> None:
        pass

    def handle_view_modified(self, view: ViewLike) -> None:
        pass

    def handle_view_saved(self, view: ViewLike) -> None:
        pass

    def handle_view_closed(self, view: ViewLike) -> None:
        pass

    def has_document_state(self, file_name: str) -> bool:
        return file_name in self._documents


class TestDocumentHandlerFactory(object):
    def for_window(self, window, workspace, configs):
        return MockDocuments()


class MockClient():
    def __init__(self, async_response=None) -> None:
        self.responses = basic_responses
        self._notifications = []  # type: List[Notification]
        self._async_response_callback = async_response

    def send_request(self, request: Request, on_success: 'Callable', on_error: 'Callable' = None) -> None:
        response = self.responses.get(request.method)
        debug("TEST: responding to", request.method, "with", response)
        if self._async_response_callback:
            self._async_response_callback(lambda: on_success(response))
        else:
            on_success(response)

    def execute_request(self, request: Request) -> 'Any':
        return self.responses.get(request.method)

    def send_notification(self, notification: Notification) -> None:
        self._notifications.append(notification)

    def on_notification(self, name, handler: 'Callable') -> None:
        pass

    def on_request(self, name, handler: 'Callable') -> None:
        pass

    def set_error_display_handler(self, handler: 'Callable') -> None:
        pass

    def set_crash_handler(self, handler: 'Callable') -> None:
        pass

    def set_log_payload_handler(self, handler: 'Callable') -> None:
        pass

    def exit(self) -> None:
        pass

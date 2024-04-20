from LSP.plugin.core.logging import debug
from LSP.plugin.core.protocol import Notification
from LSP.plugin.core.protocol import Request
from LSP.plugin.core.protocol import Response
from LSP.plugin.core.types import ClientConfig
from typing import Any, Callable, List


TEST_CONFIG = ClientConfig(name="test", command=[], selector="text.plain", tcp_port=None)
DISABLED_CONFIG = ClientConfig("test", command=[], selector="text.plain", tcp_port=None, enabled=False)

basic_responses = {
    'initialize': {
        'capabilities': {
            'testing': True,
            'hoverProvider': True,
            'completionProvider': {
                'triggerCharacters': ['.'],
                'resolveProvider': True
            },
            'textDocumentSync': {
                "openClose": True,
                "change": 2,
                "save": True
            },
            'definitionProvider': True,
            'typeDefinitionProvider': True,
            'declarationProvider': True,
            'implementationProvider': True,
            'documentFormattingProvider': True,
            'selectionRangeProvider': True,
            'renameProvider': True,
            'workspace': {
                'workspaceFolders': {
                    'supported': True
                }
            }
        }
    }
}


class MockSession(object):
    def __init__(self, async_response=None) -> None:
        self.responses = basic_responses
        self._notifications: List[Notification] = []
        self._async_response_callback = async_response

    def send_request(self, request: Request, on_success: Callable, on_error: Callable = None) -> None:
        response = self.responses.get(request.method)
        debug("TEST: responding to", request.method, "with", response)
        if self._async_response_callback:
            self._async_response_callback(lambda: on_success(response))
        else:
            on_success(response)

    def execute_request(self, request: Request) -> Any:
        return self.responses.get(request.method)

    def send_notification(self, notification: Notification) -> None:
        self._notifications.append(notification)

    def on_notification(self, name, handler: Callable) -> None:
        pass

    def on_request(self, name, handler: Callable) -> None:
        pass

    def set_error_display_handler(self, handler: Callable) -> None:
        pass

    def set_crash_handler(self, handler: Callable) -> None:
        pass

    def set_log_payload_handler(self, handler: Callable) -> None:
        pass

    def exit(self) -> None:
        pass

    def send_response(self, response: Response) -> None:
        pass

from .core.progress import ViewProgressReporter
from .core.protocol import Notification
from .core.protocol import Request
from .core.sessions import Session
from .core.settings import userprefs
from .core.typing import Any, Iterable, List, Tuple, Optional, Dict
from .core.views import DIAGNOSTIC_SEVERITY
from .core.windows import AbstractViewListener
from .session_buffer import SessionBuffer
from weakref import ref
from weakref import WeakValueDictionary
import sublime


class SessionView:
    """
    Holds state per session per view.
    """

    SHOW_DEFINITIONS_KEY = "show_definitions"
    HOVER_PROVIDER_KEY = "hoverProvider"
    HOVER_PROVIDER_COUNT_KEY = "lsp_hover_provider_count"
    AC_TRIGGERS_KEY = "auto_complete_triggers"
    COMPLETION_PROVIDER_KEY = "completionProvider"
    TRIGGER_CHARACTERS_KEY = "completionProvider.triggerCharacters"

    _session_buffers = WeakValueDictionary()  # type: WeakValueDictionary[Tuple[str, int], SessionBuffer]

    def __init__(self, listener: AbstractViewListener, session: Session) -> None:
        self.view = listener.view
        self.session = session
        self.active_requests = {}  # type: Dict[int, Request]
        self.listener = ref(listener)
        self.progress = {}  # type: Dict[int, ViewProgressReporter]
        settings = self.view.settings()
        buffer_id = self.view.buffer_id()
        key = (session.config.name, buffer_id)
        session_buffer = self._session_buffers.get(key)
        if session_buffer is None:
            session_buffer = SessionBuffer(self, buffer_id, listener.get_language_id())
            self._session_buffers[key] = session_buffer
        else:
            session_buffer.add_session_view(self)
        self.session_buffer = session_buffer
        session.register_session_view_async(self)
        session.config.set_view_status(self.view, "")
        if self.session.has_capability(self.HOVER_PROVIDER_KEY):
            self._increment_hover_count()
        self._clear_auto_complete_triggers(settings)
        self._setup_auto_complete_triggers(settings)

    def __del__(self) -> None:
        settings = self.view.settings()  # type: sublime.Settings
        self._clear_auto_complete_triggers(settings)
        if self.session.has_capability(self.HOVER_PROVIDER_KEY):
            self._decrement_hover_count()
        # If the session is exiting then there's no point in sending textDocument/didClose and there's also no point
        # in unregistering ourselves from the session.
        if not self.session.exiting:
            for request_id, request in self.active_requests.items():
                if request.view and request.view.id() == self.view.id():
                    self.session.send_notification(Notification("$/cancelRequest", {"id": request_id}))
            self.session.unregister_session_view_async(self)
        self.session.config.erase_view_status(self.view)
        for severity in reversed(range(1, len(DIAGNOSTIC_SEVERITY) + 1)):
            self.view.erase_regions(self.diagnostics_key(severity))

    def _clear_auto_complete_triggers(self, settings: sublime.Settings) -> None:
        '''Remove all of our modifications to the view's "auto_complete_triggers"'''
        triggers = settings.get(self.AC_TRIGGERS_KEY)
        if isinstance(triggers, list):
            triggers = [t for t in triggers if self.session.config.name != t.get("server", "")]
            settings.set(self.AC_TRIGGERS_KEY, triggers)

    def _setup_auto_complete_triggers(self, settings: sublime.Settings) -> None:
        """Register trigger characters from static capabilities of the server."""
        trigger_chars = self.session.get_capability(self.TRIGGER_CHARACTERS_KEY)
        if isinstance(trigger_chars, list):
            self._apply_auto_complete_triggers(settings, trigger_chars)

    def _register_auto_complete_triggers(self, registration_id: str, trigger_chars: List[str]) -> None:
        """Register trigger characters from a dynamic server registration."""
        self._apply_auto_complete_triggers(self.view.settings(), trigger_chars, registration_id)

    def _unregister_auto_complete_triggers(self, registration_id: str) -> None:
        """Remove trigger characters that were previously dynamically registered."""
        settings = self.view.settings()
        triggers = settings.get(self.AC_TRIGGERS_KEY)
        if isinstance(triggers, list):
            new_triggers = []  # type: List[Dict[str, str]]
            name = self.session.config.name
            for trigger in triggers:
                if trigger.get("server", "") == name and trigger.get("registration_id", "") == registration_id:
                    continue
                new_triggers.append(trigger)
            settings.set(self.AC_TRIGGERS_KEY, triggers)

    def _apply_auto_complete_triggers(
        self,
        settings: sublime.Settings,
        trigger_chars: List[str],
        registration_id: Optional[str] = None
    ) -> None:
        """This method actually modifies the auto_complete_triggers entries for the view."""
        selector = self.session.config.auto_complete_selector
        if not selector:
            # If the user did not set up an auto_complete_selector for this server configuration, fallback to the
            # "global" auto_complete_selector of the view.
            selector = str(settings.get("auto_complete_selector"))
        trigger = {
            "selector": selector,
            # This key is not used by Sublime, but is used as a "breadcrumb" to figure out what needs to be removed
            # from the auto_complete_triggers array once the session is stopped.
            "server": self.session.config.name
        }
        if not self.session.config.ignore_server_trigger_chars:
            trigger["characters"] = "".join(trigger_chars)
        if isinstance(registration_id, str):
            # This key is not used by Sublime, but is used as a "breadcrumb" as well, for dynamic registrations.
            trigger["registration_id"] = registration_id
        triggers = settings.get(self.AC_TRIGGERS_KEY) or []  # type: List[Dict[str, str]]
        triggers.append(trigger)
        settings.set(self.AC_TRIGGERS_KEY, triggers)

    def _increment_hover_count(self) -> None:
        settings = self.view.settings()
        count = settings.get(self.HOVER_PROVIDER_COUNT_KEY, 0)
        if isinstance(count, int):
            count += 1
            settings.set(self.HOVER_PROVIDER_COUNT_KEY, count)
            settings.set(self.SHOW_DEFINITIONS_KEY, False)

    def _decrement_hover_count(self) -> None:
        settings = self.view.settings()
        count = settings.get(self.HOVER_PROVIDER_COUNT_KEY)
        if isinstance(count, int):
            count -= 1
            if count == 0:
                settings.erase(self.HOVER_PROVIDER_COUNT_KEY)
                settings.set(self.SHOW_DEFINITIONS_KEY, True)

    def get_capability_async(self, capability_path: str) -> Optional[Any]:
        return self.session_buffer.get_capability(capability_path)

    def on_capability_added_async(self, registration_id: str, capability_path: str, options: Dict[str, Any]) -> None:
        if capability_path == self.HOVER_PROVIDER_KEY:
            self._increment_hover_count()
        elif capability_path.startswith(self.COMPLETION_PROVIDER_KEY):
            trigger_chars = options.get("triggerCharacters")
            if isinstance(trigger_chars, list):
                self._register_auto_complete_triggers(registration_id, trigger_chars)
        elif capability_path.startswith("codeLensProvider"):
            listener = self.listener()
            if listener:
                listener.on_code_lens_capability_registered_async()

    def on_capability_removed_async(self, registration_id: str, discarded: Dict[str, Any]) -> None:
        if self.HOVER_PROVIDER_KEY in discarded:
            self._decrement_hover_count()
        elif self.COMPLETION_PROVIDER_KEY in discarded:
            self._unregister_auto_complete_triggers(registration_id)

    def has_capability_async(self, capability_path: str) -> bool:
        return self.session_buffer.has_capability(capability_path)

    def shutdown_async(self) -> None:
        listener = self.listener()
        if listener:
            listener.on_session_shutdown_async(self.session)

    def diagnostics_key(self, severity: int) -> str:
        return "lsp{}d{}".format(self.session.config.name, severity)

    def present_diagnostics_async(self, flags: int) -> None:
        data_per_severity = self.session_buffer.data_per_severity
        for severity in reversed(range(1, len(DIAGNOSTIC_SEVERITY) + 1)):
            key = self.diagnostics_key(severity)
            data = data_per_severity.get(severity)
            if data is None:
                self.view.erase_regions(key)
            elif ((severity <= userprefs().show_diagnostics_severity_level) and
                    (data.icon or flags != (sublime.DRAW_NO_FILL | sublime.DRAW_NO_OUTLINE))):
                # allow showing diagnostics with same begin and end range in the view
                flags |= sublime.DRAW_EMPTY
                self.view.add_regions(key, data.regions, data.scope, data.icon, flags)
            else:
                self.view.erase_regions(key)
        listener = self.listener()
        if listener:
            listener.on_diagnostics_updated_async()

    def on_request_started_async(self, request_id: int, request: Request) -> None:
        self.active_requests[request_id] = request
        if request.progress:
            self.progress[request_id] = ViewProgressReporter(
                view=self.view,
                key="lspprogressview{}{}".format(self.session.config.name, request_id),
                title=request.method
            )

    def on_request_finished_async(self, request_id: int) -> None:
        self.active_requests.pop(request_id, None)
        self.progress.pop(request_id, None)

    def on_request_progress(self, request_id: int, params: Dict[str, Any]) -> None:
        value = params['value']
        kind = value['kind']
        if kind == 'begin':
            progress = self.progress[request_id]
            progress.title = value["title"]
            progress(value.get("message"), value.get("percentage"))
        elif kind == 'report':
            self.progress[request_id](value.get("message"), value.get("percentage"))

    def on_text_changed_async(self, change_count: int, changes: Iterable[sublime.TextChange]) -> None:
        self.session_buffer.on_text_changed_async(self.view, change_count, changes)

    def on_revert_async(self) -> None:
        self.session_buffer.on_revert_async(self.view)

    def on_reload_async(self) -> None:
        self.session_buffer.on_reload_async(self.view)

    def purge_changes_async(self) -> None:
        self.session_buffer.purge_changes_async(self.view)

    def on_pre_save_async(self, old_file_name: str) -> None:
        self.session_buffer.on_pre_save_async(self.view, old_file_name)

    def on_post_save_async(self) -> None:
        self.session_buffer.on_post_save_async(self.view)

    def __str__(self) -> str:
        return '{}:{}'.format(self.session.config.name, self.view.id())

from .code_lens import CodeLensView
from .core.progress import ViewProgressReporter
from .core.promise import Promise
from .core.protocol import CodeLens
from .core.protocol import DiagnosticTag
from .core.protocol import Notification
from .core.protocol import Request
from .core.sessions import Session
from .core.settings import userprefs
from .core.types import debounced
from .core.typing import Any, Iterable, List, Tuple, Optional, Dict, Generator
from .core.views import DIAGNOSTIC_SEVERITY
from .core.views import text_document_identifier
from .core.windows import AbstractViewListener
from .session_buffer import SessionBuffer
from weakref import ref
from weakref import WeakValueDictionary
import sublime
import functools

DIAGNOSTIC_TAG_VALUES = [v for (k, v) in DiagnosticTag.__dict__.items() if not k.startswith('_')]


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

    _session_buffers = WeakValueDictionary()  # type: WeakValueDictionary[Tuple[str, int, int], SessionBuffer]

    def __init__(self, listener: AbstractViewListener, session: Session) -> None:
        self.view = listener.view
        self.session = session
        self.active_requests = {}  # type: Dict[int, Request]
        self.listener = ref(listener)
        self.progress = {}  # type: Dict[int, ViewProgressReporter]
        self._code_lenses = CodeLensView(self.view)
        settings = self.view.settings()
        buffer_id = self.view.buffer_id()
        key = (session.config.name, session.window.id(), buffer_id)
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
        self._code_lenses.clear_view()
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
            self.view.erase_regions(self.diagnostics_key(severity, False))
            self.view.erase_regions(self.diagnostics_key(severity, True))

    def _clear_auto_complete_triggers(self, settings: sublime.Settings) -> None:
        '''Remove all of our modifications to the view's "auto_complete_triggers"'''
        triggers = settings.get(self.AC_TRIGGERS_KEY)
        if isinstance(triggers, list):
            triggers = [t for t in triggers if self.session.config.name != t.get("server", "")]
            settings.set(self.AC_TRIGGERS_KEY, triggers)

    def _setup_auto_complete_triggers(self, settings: sublime.Settings) -> None:
        """Register trigger characters from static capabilities of the server."""
        trigger_chars = self.session.get_capability(self.TRIGGER_CHARACTERS_KEY)
        if isinstance(trigger_chars, list) or self.session.config.auto_complete_selector:
            self._apply_auto_complete_triggers(settings, trigger_chars or [])

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
        if trigger_chars:
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
            if isinstance(trigger_chars, list) or self.session.config.auto_complete_selector:
                self._register_auto_complete_triggers(registration_id, trigger_chars or [])
        elif capability_path.startswith("codeLensProvider"):
            listener = self.listener()
            if listener:
                listener.on_code_lens_capability_registered_async()

    def on_capability_removed_async(self, registration_id: str, discarded_capabilities: Dict[str, Any]) -> None:
        if self.HOVER_PROVIDER_KEY in discarded_capabilities:
            self._decrement_hover_count()
        elif self.COMPLETION_PROVIDER_KEY in discarded_capabilities:
            self._unregister_auto_complete_triggers(registration_id)

    def has_capability_async(self, capability_path: str) -> bool:
        return self.session_buffer.has_capability(capability_path)

    def shutdown_async(self) -> None:
        listener = self.listener()
        if listener:
            listener.on_session_shutdown_async(self.session)

    def diagnostics_key(self, severity: int, multiline: bool) -> str:
        return "lsp{}d{}{}".format(self.session.config.name, "m" if multiline else "s", severity)

    def diagnostics_tag_scope(self, tag: int) -> Optional[str]:
        for k, v in DiagnosticTag.__dict__.items():
            if v == tag:
                return 'markup.{}.lsp'.format(k.lower())
        return None

    def present_diagnostics_async(self) -> None:
        flags = 0 if userprefs().show_diagnostics_highlights else sublime.DRAW_NO_FILL | sublime.DRAW_NO_OUTLINE
        level = userprefs().show_diagnostics_severity_level
        for sev in reversed(range(1, len(DIAGNOSTIC_SEVERITY) + 1)):
            self._draw_diagnostics(sev, level, DIAGNOSTIC_SEVERITY[sev - 1][4] if flags == 0 else flags, False)
            self._draw_diagnostics(sev, level, DIAGNOSTIC_SEVERITY[sev - 1][5] if flags == 0 else flags, True)
        listener = self.listener()
        if listener:
            listener.on_diagnostics_updated_async()

    def _draw_diagnostics(self, severity: int, max_severity_level: int, flags: int, multiline: bool) -> None:
        key = self.diagnostics_key(severity, multiline)
        key_tags = {tag: '{}_tags_{}'.format(key, tag) for tag in DIAGNOSTIC_TAG_VALUES}
        for key_tag in key_tags.values():
            self.view.erase_regions(key_tag)
        data = self.session_buffer.data_per_severity.get((severity, multiline))
        # TODO: Why do we have this data.icon check?
        if data and data.icon and severity <= max_severity_level:
            non_tag_regions = data.regions
            for tag, regions in data.regions_with_tag.items():
                tag_scope = self.diagnostics_tag_scope(tag)
                # Trick to only add tag regions if there is a corresponding color scheme scope defined.
                if tag_scope and 'background' in self.view.style_for_scope(tag_scope):
                    self.view.add_regions(key_tags[tag], regions, tag_scope, flags=sublime.DRAW_NO_OUTLINE)
                else:
                    non_tag_regions.extend(regions)
            self.view.add_regions(key, non_tag_regions, data.scope, data.icon, flags)
        else:
            self.view.erase_regions(key)

    def on_request_started_async(self, request_id: int, request: Request) -> None:
        self.active_requests[request_id] = request
        if request.progress:
            debounced(
                functools.partial(self._start_progress_reporter_async, request_id, request.method),
                timeout_ms=200,
                condition=lambda: request_id in self.active_requests and request_id not in self.progress,
                async_thread=True
            )

    def on_request_finished_async(self, request_id: int) -> None:
        self.active_requests.pop(request_id, None)
        self.progress.pop(request_id, None)

    def on_request_progress(self, request_id: int, params: Dict[str, Any]) -> None:
        value = params['value']
        kind = value['kind']
        if kind == 'begin':
            title = value["title"]
            progress = self.progress.get(request_id)
            if not progress:
                progress = self._start_progress_reporter_async(request_id, title)
            progress.title = title
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

    def _start_progress_reporter_async(self, request_id: int, title: str) -> ViewProgressReporter:
        progress = ViewProgressReporter(
            view=self.view,
            key="lspprogressview{}{}".format(self.session.config.name, request_id),
            title=title
        )
        self.progress[request_id] = progress
        return progress

    # --- textDocument/codeLens ----------------------------------------------------------------------------------------

    def start_code_lenses_async(self) -> None:
        params = {'textDocument': text_document_identifier(self.view)}
        for request_id, request in self.active_requests.items():
            if request.method == "codeAction/resolve":
                self.session.send_notification(Notification("$/cancelRequest", {"id": request_id}))
        self.session.send_request_async(
            Request("textDocument/codeLens", params, self.view),
            self._on_code_lenses_async
        )

    def _on_code_lenses_async(self, response: Optional[List[CodeLens]]) -> None:
        self._code_lenses.clear_annotations()
        if not isinstance(response, list):
            return
        self._code_lenses.handle_response(self.session.config.name, response)
        self.resolve_visible_code_lenses_async()

    def resolve_visible_code_lenses_async(self) -> None:
        if self._code_lenses.is_empty():
            return
        promises = []  # type: List[Promise[None]]
        for code_lens in self._code_lenses.unresolved_visible_code_lens(self.view.visible_region()):
            callback = functools.partial(code_lens.resolve, self.view)
            promise = self.session.send_request_task(
                Request("codeLens/resolve", code_lens.data, self.view)
            ).then(callback)
            promises.append(promise)
        Promise.all(promises).then(lambda _: self._code_lenses.render())

    def get_resolved_code_lenses_for_region(self, region: sublime.Region) -> Generator[CodeLens, None, None]:
        yield from self._code_lenses.get_resolved_code_lenses_for_region(region)

    def __str__(self) -> str:
        return '{}:{}'.format(self.session.config.name, self.view.id())

from __future__ import annotations

from ..protocol import Command
from ..protocol import DocumentUri
from .core.active_request import ActiveRequest
from .core.constants import DIAGNOSTIC_TAG_SCOPES
from .core.constants import DOCUMENT_HIGHLIGHT_KIND_NAMES
from .core.constants import HOVER_ENABLED_KEY
from .core.constants import RegionKey
from .core.constants import REGIONS_INITIALIZE_FLAGS
from .core.constants import RequestFlags
from .core.constants import SHOW_DEFINITIONS_KEY
from .core.protocol import Request
from .core.protocol import ResolvedCodeLens
from .core.sessions import AbstractViewListener
from .core.sessions import Session
from .core.settings import userprefs
from .core.views import DIAGNOSTIC_SEVERITY
from .core.views import make_command_link
from .core.views import range_to_region
from .diagnostics import DiagnosticsAnnotationsView
from .session_buffer import SessionBuffer
from typing import Any
from typing import Iterable
from weakref import ref
from weakref import WeakValueDictionary
import html
import itertools
import sublime


class TagData:
    __slots__ = ('key', 'regions', 'scope')

    def __init__(self, key: str, regions: list[sublime.Region] = [], scope: str = '') -> None:
        self.key = key
        self.regions = regions
        self.scope = scope


class SessionView:
    """
    Holds state per session per view.
    """

    HOVER_PROVIDER_KEY = "hoverProvider"
    AC_TRIGGERS_KEY = "auto_complete_triggers"
    COMPLETION_PROVIDER_KEY = "completionProvider"
    TRIGGER_CHARACTERS_KEY = "completionProvider.triggerCharacters"

    _session_buffers: WeakValueDictionary[tuple[int, int], SessionBuffer] = WeakValueDictionary()

    def __init__(self, listener: AbstractViewListener, session: Session, uri: DocumentUri) -> None:
        self._view = listener.view
        self._session = session
        self._diagnostic_annotations = DiagnosticsAnnotationsView(self._view, session.config.name)
        self._initialize_region_keys()
        self._active_requests: dict[int, ActiveRequest] = {}
        self._listener = ref(listener)
        self._code_lenses: list[ResolvedCodeLens] = []
        self._code_lens_phantoms = sublime.PhantomSet(self.view, self._code_lens_key())
        self.code_lenses_needs_refresh = False
        settings = self._view.settings()
        buffer_id = self._view.buffer_id()
        key = (id(session), buffer_id)
        session_buffer = self._session_buffers.get(key)
        if session_buffer is None:
            session_buffer = SessionBuffer(self, buffer_id, uri)
            self._session_buffers[key] = session_buffer
            self._session_buffer = session_buffer
            self._session.register_session_buffer_async(session_buffer)
        else:
            self._session_buffer = session_buffer
            session_buffer.add_session_view(self)
        session.register_session_view_async(self)
        session.config.set_view_status(self._view, session.config_status_message)
        if self._session.has_capability(self.HOVER_PROVIDER_KEY):
            self._increment_hover_count()
        self._clear_auto_complete_triggers(settings)
        self._setup_auto_complete_triggers(settings)

    def on_before_remove(self) -> None:
        settings: sublime.Settings = self.view.settings()
        self._clear_auto_complete_triggers(settings)
        self.clear_code_lenses_async()
        if self.session.has_capability(self.HOVER_PROVIDER_KEY):
            self._decrement_hover_count()
        # If the session is exiting then there's no point in sending textDocument/didClose and there's also no point
        # in unregistering ourselves from the session.
        if not self.session.exiting:
            for request_id, data in self._active_requests.items():
                if data.request.view and not data.canceled:
                    self.session.cancel_request_async(request_id)
            self.session.unregister_session_view_async(self)
        self.session.config.erase_view_status(self.view)
        for severity in reversed(range(1, len(DIAGNOSTIC_SEVERITY) + 1)):
            self.view.erase_regions(f"{self.diagnostics_key(severity, False)}_icon")
            self.view.erase_regions(f"{self.diagnostics_key(severity, False)}_underline")
            self.view.erase_regions(f"{self.diagnostics_key(severity, True)}_icon")
            self.view.erase_regions(f"{self.diagnostics_key(severity, True)}_underline")
        self.view.erase_regions(RegionKey.DOCUMENT_LINK)
        self.session_buffer.remove_session_view(self)
        if listener := self.listener():
            listener.on_diagnostics_updated_async(False)

    def on_initialized(self) -> None:
        self.session_buffer.on_session_view_initialized(self._view)

    @property
    def session(self) -> Session:
        return self._session

    @property
    def view(self) -> sublime.View:
        return self._view

    @property
    def listener(self) -> ref[AbstractViewListener]:
        return self._listener

    @property
    def session_buffer(self) -> SessionBuffer:
        return self._session_buffer

    @property
    def active_requests(self) -> dict[int, ActiveRequest]:
        return self._active_requests

    def _is_listener_alive(self) -> bool:
        return bool(self.listener())

    def _initialize_region_keys(self) -> None:
        """
        Initialize all region keys for the View.add_regions method to enforce a certain draw order for overlapping
        diagnostics, semantic tokens, document highlights, and gutter icons. The draw order seems to follow the
        following rules:
          - inline decorations (underline & background) from region keys which were initialized _last_ are drawn on top
          - gutter icons from region keys which were initialized _first_ are drawn
        For more context, see https://github.com/sublimelsp/LSP/issues/1593.
        """
        keys: list[str] = []
        r = [sublime.Region(0, 0)]
        document_highlight_style = userprefs().document_highlight_style
        hover_highlight_style = userprefs().hover_highlight_style
        line_modes = ["m", "s"]
        self.view.add_regions(RegionKey.CODE_ACTION, r)  # code actions lightbulb icon should always be on top
        session_name = self.session.config.name
        for key in range(1, 100):
            keys.append(f"lsp_semantic_{session_name}_{key}")
        if document_highlight_style in ("background", "fill"):
            for kind in DOCUMENT_HIGHLIGHT_KIND_NAMES.values():
                for mode in line_modes:
                    keys.append(f"lsp_highlight_{kind}{mode}")
        if hover_highlight_style in ("background", "fill"):
            keys.append(RegionKey.HOVER_HIGHLIGHT)
        for severity in range(1, 5):
            for mode in line_modes:
                for tag in range(1, 3):
                    keys.append(f"lsp{session_name}d{mode}{severity}_tags_{tag}")
        keys.append(RegionKey.DOCUMENT_LINK)
        for severity in range(1, 5):
            for mode in line_modes:
                keys.append(f"lsp{session_name}d{mode}{severity}_icon")
        for severity in range(4, 0, -1):
            for mode in line_modes:
                keys.append(f"lsp{session_name}d{mode}{severity}_underline")
        if document_highlight_style in ("underline", "stippled"):
            for kind in DOCUMENT_HIGHLIGHT_KIND_NAMES.values():
                for mode in line_modes:
                    keys.append(f"lsp_highlight_{kind}{mode}")
        if hover_highlight_style in ("underline", "stippled"):
            keys.append(RegionKey.HOVER_HIGHLIGHT)
        for key in keys:
            self.view.add_regions(key, r, flags=REGIONS_INITIALIZE_FLAGS)
        self._diagnostic_annotations.initialize_region_keys()

    def _clear_auto_complete_triggers(self, settings: sublime.Settings) -> None:
        '''Remove all of our modifications to the view's "auto_complete_triggers"'''
        triggers = settings.get(self.AC_TRIGGERS_KEY)
        if isinstance(triggers, list):
            triggers = [t for t in triggers if isinstance(t, dict) and self.session.config.name != t.get("server", "")]
            settings.set(self.AC_TRIGGERS_KEY, triggers)

    def _setup_auto_complete_triggers(self, settings: sublime.Settings) -> None:
        """Register trigger characters from static capabilities of the server."""
        trigger_chars = self.session.get_capability(self.TRIGGER_CHARACTERS_KEY)
        if isinstance(trigger_chars, list) or self.session.config.auto_complete_selector:
            self._apply_auto_complete_triggers(settings, trigger_chars or [])

    def _register_auto_complete_triggers(self, registration_id: str, trigger_chars: list[str]) -> None:
        """Register trigger characters from a dynamic server registration."""
        self._apply_auto_complete_triggers(self.view.settings(), trigger_chars, registration_id)

    def _unregister_auto_complete_triggers(self, registration_id: str) -> None:
        """Remove trigger characters that were previously dynamically registered."""
        settings = self.view.settings()
        triggers = settings.get(self.AC_TRIGGERS_KEY)
        if isinstance(triggers, list):
            new_triggers: list[dict[str, str]] = []
            name = self.session.config.name
            for trigger in triggers:
                if not isinstance(trigger, dict):
                    continue
                if trigger.get("server", "") == name and trigger.get("registration_id", "") == registration_id:
                    continue
                new_triggers.append(trigger)
            settings.set(self.AC_TRIGGERS_KEY, triggers)

    def _apply_auto_complete_triggers(
        self,
        settings: sublime.Settings,
        trigger_chars: list[str],
        registration_id: str | None = None
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
        triggers: list[dict[str, str]] = settings.get(self.AC_TRIGGERS_KEY) or []
        triggers.append(trigger)
        settings.set(self.AC_TRIGGERS_KEY, triggers)

    def _increment_hover_count(self) -> None:
        listener = self.listener()
        if not listener:
            return
        listener.hover_provider_count += 1
        if (window := self.view.window()) and window.settings().get(HOVER_ENABLED_KEY, True):
            self.view.settings().set(SHOW_DEFINITIONS_KEY, False)

    def _decrement_hover_count(self) -> None:
        listener = self.listener()
        if not listener:
            return
        listener.hover_provider_count -= 1
        if listener.hover_provider_count == 0:
            self.reset_show_definitions()

    def reset_show_definitions(self) -> None:
        self.view.settings().erase(SHOW_DEFINITIONS_KEY)

    def get_uri(self) -> DocumentUri | None:
        listener = self.listener()
        return listener.get_uri() if listener else None

    def get_language_id(self) -> str | None:
        listener = self.listener()
        return listener.get_language_id() if listener else None

    def get_view_for_group(self, group: int) -> sublime.View | None:
        sheet = self.view.sheet()
        return self.view if sheet and sheet.group() == group else None

    def get_capability_async(self, capability_path: str) -> Any | None:
        return self.session_buffer.get_capability(capability_path)

    def get_request_flags(self) -> RequestFlags:
        if listener := self.listener():
            return listener.get_request_flags(self.session)
        return RequestFlags.NONE

    def on_capability_added_async(self, registration_id: str, capability_path: str, options: dict[str, Any]) -> None:
        if capability_path == self.HOVER_PROVIDER_KEY:
            self._increment_hover_count()
        elif capability_path.startswith(self.COMPLETION_PROVIDER_KEY):
            trigger_chars = options.get("triggerCharacters")
            if isinstance(trigger_chars, list) or self.session.config.auto_complete_selector:
                self._register_auto_complete_triggers(registration_id, trigger_chars or [])

    def on_capability_removed_async(self, registration_id: str, discarded_capabilities: dict[str, Any]) -> None:
        if self.HOVER_PROVIDER_KEY in discarded_capabilities:
            self._decrement_hover_count()
        elif self.COMPLETION_PROVIDER_KEY in discarded_capabilities:
            self._unregister_auto_complete_triggers(registration_id)

    def has_capability_async(self, capability_path: str) -> bool:
        return self.session_buffer.has_capability(capability_path)

    def shutdown_async(self) -> None:
        if listener := self.listener():
            listener.on_session_shutdown_async(self.session)

    def diagnostics_key(self, severity: int, multiline: bool) -> str:
        return "lsp{}d{}{}".format(self.session.config.name, "m" if multiline else "s", severity)

    def present_diagnostics_async(self, is_view_visible: bool) -> None:
        self._redraw_diagnostics_async()
        if listener := self.listener():
            listener.on_diagnostics_updated_async(is_view_visible)

    def _redraw_diagnostics_async(self) -> None:
        flags = userprefs().diagnostics_highlight_style_flags()  # for single lines
        multiline_flags = None if userprefs().show_multiline_diagnostics_highlights else sublime.RegionFlags.DRAW_NO_FILL | sublime.RegionFlags.DRAW_NO_OUTLINE | sublime.RegionFlags.NO_UNDO  # noqa: E501
        level = userprefs().show_diagnostics_severity_level
        for sev in reversed(range(1, len(DIAGNOSTIC_SEVERITY) + 1)):
            self._draw_diagnostics(sev, level, flags[sev - 1] or DIAGNOSTIC_SEVERITY[sev - 1][4], multiline=False)
            self._draw_diagnostics(sev, level, multiline_flags or DIAGNOSTIC_SEVERITY[sev - 1][5], multiline=True)
        self._diagnostic_annotations.draw(self.session_buffer.diagnostics)

    def _draw_diagnostics(
        self,
        severity: int,
        max_severity_level: int,
        flags: sublime.RegionFlags,
        multiline: bool
    ) -> None:
        ICON_FLAGS = sublime.RegionFlags.HIDE_ON_MINIMAP | sublime.RegionFlags.DRAW_NO_FILL | sublime.RegionFlags.DRAW_NO_OUTLINE | sublime.RegionFlags.NO_UNDO  # noqa: E501
        key = self.diagnostics_key(severity, multiline)
        tags = {tag: TagData(f'{key}_tags_{tag}') for tag in DIAGNOSTIC_TAG_SCOPES}
        data = self._session_buffer.diagnostics_data_per_severity.get((severity, multiline))
        if data and severity <= max_severity_level:
            non_tag_regions = data.regions
            for tag, regions in data.regions_with_tag.items():
                tag_scope = DIAGNOSTIC_TAG_SCOPES[tag]
                # Only add tag regions if there is a corresponding color scheme scope defined
                if tag in self.session_buffer.supported_diagnostic_tags:
                    tags[tag].regions = regions
                    tags[tag].scope = tag_scope
                else:
                    non_tag_regions.extend(regions)
            self.view.add_regions(f"{key}_icon", non_tag_regions, data.scope, data.icon, ICON_FLAGS)
            self.view.add_regions(f"{key}_underline", non_tag_regions, data.scope, "", flags)
        else:
            self.view.erase_regions(f"{key}_icon")
            self.view.erase_regions(f"{key}_underline")
        for data in tags.values():
            if data.regions:
                self.view.add_regions(
                    data.key,
                    data.regions,
                    data.scope,
                    flags=sublime.RegionFlags.DRAW_NO_OUTLINE | sublime.RegionFlags.NO_UNDO
                )
            else:
                self.view.erase_regions(data.key)

    def on_request_started_async(self, request_id: int, request: Request[Any, Any]) -> None:
        self._active_requests[request_id] = ActiveRequest(self, request_id, request)

    def on_request_finished_async(self, request_id: int) -> None:
        self._active_requests.pop(request_id, None)

    def on_request_canceled_async(self, request_id: int) -> None:
        if active_request := self._active_requests.get(request_id):
            active_request.on_request_canceled_async()

    def on_request_progress(self, request_id: int, params: dict[str, Any]) -> None:
        if request := self._active_requests.get(request_id, None):
            request.update_progress_async(params)

    def on_text_changed_async(self, change_count: int, changes: Iterable[sublime.TextChange]) -> None:
        self.session_buffer.on_text_changed_async(self.view, change_count, changes)

    def on_revert_async(self) -> None:
        self.session_buffer.on_revert_async(self.view)

    def on_reload_async(self) -> None:
        self.session_buffer.on_reload_async(self.view)

    def purge_changes_async(self) -> None:
        self.session_buffer.purge_changes_async(self.view)

    def on_pre_save_async(self) -> None:
        self.session_buffer.on_pre_save_async(self.view)

    def on_post_save_async(self, new_uri: DocumentUri) -> None:
        self.session_buffer.on_post_save_async(self.view, new_uri)

    def on_userprefs_changed_async(self) -> None:
        self._redraw_diagnostics_async()
        self._redraw_code_lenses_async(clear=True)

    def on_color_scheme_changed(self) -> None:
        self._diagnostic_annotations.on_color_scheme_changed()

    # --- textDocument/codeLens ----------------------------------------------------------------------------------------

    def handle_code_lenses_async(self, code_lenses: list[ResolvedCodeLens]) -> None:
        if self._code_lenses or code_lenses:
            self._code_lenses = code_lenses
            self._redraw_code_lenses_async()

    def clear_code_lenses_async(self) -> None:
        self._code_lens_phantoms.update([])
        self.view.erase_regions(self._code_lens_key())

    def _redraw_code_lenses_async(self, *, clear: bool = False) -> None:
        if clear:
            self.clear_code_lenses_async()
        if userprefs().show_code_lens == 'annotation':
            key = self._code_lens_key()
            regions = [self._code_lens_region(code_lens) for code_lens in self._code_lenses]
            flags = sublime.RegionFlags.NO_UNDO
            annotations = [self._code_lens_annotation(code_lens) for code_lens in self._code_lenses]
            annotation_color = self.session_buffer.code_lens_annotation_color
            self.view.add_regions(key, regions, flags=flags, annotations=annotations, annotation_color=annotation_color)
        elif userprefs().show_code_lens == 'phantom':
            # Workaround for https://github.com/sublimehq/sublime_text/issues/6188
            # Phantoms added to a particular view also show up on all clones, so we only draw phantoms on the primary
            # view. Note that when the primary view gets closed, another clone automatically becomes the primary view.
            if not self.view.is_primary():
                return
            phantoms: list[sublime.Phantom] = []
            for region, group in itertools.groupby(self._code_lenses, key=self._code_lens_region):
                phantom_region = self._get_phantom_region(region)
                html = '<body id="lsp-code-lens">{}</body>'.format(
                    '\n<small style="font-family: system">|</small>\n'.join(
                        self._code_lens_annotation(code_lens) for code_lens in group
                    )
                )
                phantoms.append(sublime.Phantom(phantom_region, html, sublime.PhantomLayout.BELOW))
            self._code_lens_phantoms.update(phantoms)

    def _code_lens_key(self) -> str:
        return f'lsp_code_lens.{self.session.config.name}'

    def _code_lens_region(self, code_lens: ResolvedCodeLens) -> sublime.Region:
        return range_to_region(code_lens['range'], self.view)

    def _code_lens_annotation(self, code_lens: ResolvedCodeLens) -> str:
        command = code_lens['command']
        if code_lens.get('uses_cached_command', False):
            # Only show the cached command title but don't create a clickable link until the code lens gets resolved
            # with the actual command.
            annotation = html.escape(command['title'])
        else:
            annotation = make_command_link('lsp_execute', command['title'], {
                'session_name': self.session.config.name,
                'command_name': command['command'],
                'command_args': command.get('arguments', [])
            }, view_id=self.view.id())
        return f'<small style="font-family: system">{annotation}</small>'

    def _get_phantom_region(self, region: sublime.Region) -> sublime.Region:
        line = self.view.line(region)
        offset = 0
        for ch in self.view.substr(line):
            if ch.isspace():
                offset += 1
            else:
                break
        return sublime.Region(line.a + offset, line.b)

    def get_code_lenses_for_region(self, region: sublime.Region) -> list[Command]:
        return [
            code_lens['command']
            for code_lens in self._code_lenses
            if not code_lens.get('uses_cached_command', False) and self._code_lens_region(code_lens).intersects(region)
        ]

    # ------------------------------------------------------------------------------------------------------------------

    def __str__(self) -> str:
        return f'{self.session.config.name}:{self.view.id()}'

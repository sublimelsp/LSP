from __future__ import annotations

from ....protocol import CodeAction
from ....protocol import Command
from ....protocol import Diagnostic
from ....protocol import DiagnosticRelatedInformation
from ....protocol import DiagnosticSeverity
from ....protocol import DiagnosticTag
from ....protocol import MarkupContent
from ..constants import ST_PLATFORM
from ..css import css as lsp_css
from ..settings import userprefs
from ..url import encode_code_action_uri
from ._html import _html_element
from ._html import FORMAT_MARKUP_CONTENT
from ._html import html_wrapper
from ._html import lightbulb_html
from ._html import make_link
from ._html import minihtml
from ._html import text2html
from ._uri import location_to_href
from ._uri import location_to_human_readable
from dataclasses import dataclass
from operator import itemgetter
from typing import Sequence
from typing import TYPE_CHECKING
import html
import itertools
import sublime

if TYPE_CHECKING:
    from ..sessions import SessionBufferProtocol
    from ..types import ClientConfig


_baseflags = sublime.RegionFlags.DRAW_NO_FILL | sublime.RegionFlags.DRAW_NO_OUTLINE | sublime.RegionFlags.DRAW_EMPTY_AS_OVERWRITE | sublime.RegionFlags.NO_UNDO  # noqa: E501
_multilineflags = sublime.RegionFlags.DRAW_NO_FILL | sublime.RegionFlags.NO_UNDO


@dataclass
class DiagnosticStyle:
    kind: str
    css_class: str
    region_scope: str
    icon_resource: str
    single_line_region_flags: sublime.RegionFlags
    multi_line_region_flags: sublime.RegionFlags


DIAGNOSTIC_STYLES: dict[DiagnosticSeverity, DiagnosticStyle] = {
    DiagnosticSeverity.Error: DiagnosticStyle(
        'error',
        'error',
        'region.redish markup.error.lsp',
        'Packages/LSP/icons/error.png',
        _baseflags | sublime.RegionFlags.DRAW_SQUIGGLY_UNDERLINE,
        _multilineflags
    ),
    DiagnosticSeverity.Warning: DiagnosticStyle(
        'warning',
        'warning',
        'region.yellowish markup.warning.lsp',
        'Packages/LSP/icons/warning.png',
        _baseflags | sublime.RegionFlags.DRAW_SQUIGGLY_UNDERLINE,
        _multilineflags
    ),
    DiagnosticSeverity.Information: DiagnosticStyle(
        'info',
        'information',
        'region.bluish markup.info.lsp',
        'Packages/LSP/icons/info.png',
        _baseflags | sublime.RegionFlags.DRAW_STIPPLED_UNDERLINE,
        _multilineflags
    ),
    DiagnosticSeverity.Hint: DiagnosticStyle(
        'hint',
        'hint',
        'region.bluish markup.info.hint.lsp',
        '',
        _baseflags | sublime.RegionFlags.DRAW_STIPPLED_UNDERLINE,
        _multilineflags
    ),
}


class DiagnosticSeverityData:

    __slots__ = ('regions', 'regions_with_tag', 'annotations')

    def __init__(self) -> None:
        self.regions: list[sublime.Region] = []
        self.regions_with_tag: dict[DiagnosticTag, list[sublime.Region]] = {}
        self.annotations: list[str] = []


def diagnostic_severity(diagnostic: Diagnostic) -> DiagnosticSeverity:
    return diagnostic.get("severity", DiagnosticSeverity.Error)


def diagnostic_icon(severity: DiagnosticSeverity) -> str:
    if userprefs().diagnostics_gutter_marker == "sign":
        return DIAGNOSTIC_STYLES[severity].icon_resource
    return "" if severity == DiagnosticSeverity.Hint else userprefs().diagnostics_gutter_marker


def diagnostic_source_and_code(diagnostic: Diagnostic) -> tuple[str, str | None, str | None]:
    formatted = diagnostic.get("source", "")
    href = None
    code = diagnostic.get("code")
    if code is not None:
        code = str(code)
        if code_description := diagnostic.get("codeDescription"):
            href = code_description["href"]
        else:
            formatted += f"({code})"
    return formatted, code, href


def _format_diagnostic_message(view: sublime.View, message: str | MarkupContent) -> str:
    return minihtml(view, message, FORMAT_MARKUP_CONTENT) if isinstance(message, dict) else text2html(message)


def _format_diagnostic_related_info(
    config: ClientConfig,
    info: DiagnosticRelatedInformation,
    base_dir: str | None = None
) -> str:
    location = info["location"]
    return '<a href="{}">{}</a>: {}'.format(
        location_to_href(config, location),
        text2html(location_to_human_readable(config, base_dir, location)),
        text2html(info["message"])
    )


def format_diagnostics_for_annotation(view: sublime.View, diagnostics: list[Diagnostic], css_class: str) -> list[str]:
    annotations = []
    for diagnostic in diagnostics:
        message = _format_diagnostic_message(view, diagnostic['message'])
        source = diagnostic.get('source')
        line = f'{message} <span class="color-muted">{text2html(source)}</span>' if source else message
        content = (f'<body id="lsp-annotation" class="{ST_PLATFORM}"><style>{lsp_css().annotations}</style>'
                   f'<div class="{css_class}">{line}</div></body>')
        annotations.append(content)
    return annotations


def format_diagnostic_for_panel(diagnostic: Diagnostic) -> tuple[str, int | None, str | None, str | None]:
    """
    Turn an LSP diagnostic into a string suitable for an output panel.

    :param      diagnostic:  The diagnostic
    :returns:   Tuple of (content, optional offset, optional code, optional href)
                When the last three elements are optional, don't show an inline phantom
                When the last three elements are not optional, show an inline phantom
                using the information given.
    """
    formatted, code, href = diagnostic_source_and_code(diagnostic)
    message = diagnostic['message']
    lines = (message['value'] if isinstance(message, dict) else message).splitlines() or [""]
    result = " {:>4}:{:<4}{:<8}{}".format(
        diagnostic["range"]["start"]["line"] + 1,
        diagnostic["range"]["start"]["character"] + 1,
        DIAGNOSTIC_STYLES[diagnostic_severity(diagnostic)].kind,
        lines[0]
    )
    if formatted or code is not None:
        # \u200B is the zero-width space
        result += f" \u200B{formatted}"
    offset = len(result) if href else None
    for line in itertools.islice(lines, 1, None):
        result += "\n" + 18 * " " + line
    return result, offset, code, href


def format_diagnostic_for_html(
    view: sublime.View,
    config: ClientConfig,
    diagnostic: Diagnostic,
    code_actions: list[Command | CodeAction],
    lightbulb_color: str,
    base_dir: str | None = None
) -> str:
    message = diagnostic['message']
    raw_message = message['value'] if isinstance(message, dict) else message
    content = _format_diagnostic_message(view, message)
    code = diagnostic.get("code")
    source = diagnostic.get("source")
    copy_text = raw_message.replace(' ', ' ')
    if source or code is not None:
        meta_info = ""
        if source:
            meta_info += text2html(source)
            copy_text += f' ({source})' if code is None else f' ({source}[{code}])'
        if code is not None:
            if code_description := diagnostic.get("codeDescription"):
                href = code_description["href"]
                meta_info += f'({make_link(href, str(code), tooltip=html.escape(href))})'
            else:
                meta_info += f'({text2html(str(code))})'
        content += " " + _html_element("span", meta_info, class_name="color-muted", escape=False)
    content += f"""<a class='copy-icon' title='Copy to clipboard' href='{sublime.command_url(
        'lsp_copy_text', {'text': copy_text}
    )}'>⧉</a>"""
    if related_infos := diagnostic.get("relatedInformation"):
        info = "<br>".join(_format_diagnostic_related_info(config, info, base_dir) for info in related_infos)
        content += '<hr>' + _html_element("div", info, escape=False)
    if code_actions:
        version = view.change_count()
        for code_action in sorted(code_actions, key=lambda a: a.get('isPreferred', False), reverse=True):
            icon = lightbulb_html(lightbulb_color, code_action.get('isPreferred', False))
            code_action_uri = encode_code_action_uri(config.name, version, code_action)
            content += '<hr>' + icon + make_link(code_action_uri, code_action['title'], tooltip='Run Code Action')
    severity_class = DIAGNOSTIC_STYLES[diagnostic_severity(diagnostic)].css_class
    return html_wrapper(content, class_name=severity_class)


def format_diagnostics_for_html(
    view: sublime.View,
    diagnostics_by_config: Sequence[tuple[SessionBufferProtocol, Sequence[Diagnostic]]],
    code_actions_by_config: dict[str, list[Command | CodeAction]],
    lightbulb_color: str,
    base_dir: str | None = None
) -> str:
    diagnostics_html: list[tuple[DiagnosticSeverity, str]] = []
    for sb, diagnostics in diagnostics_by_config:
        actions_for_config = code_actions_by_config.get(sb.session.config.name, [])
        single_diagnostic = len(diagnostics) == 1
        for diagnostic in diagnostics:
            code_actions = actions_for_config if single_diagnostic else [
                action for action in actions_for_config if diagnostic in action.get('diagnostics', [])
            ]
            diagnostic_html = format_diagnostic_for_html(
                view, sb.session.config, diagnostic, code_actions, lightbulb_color, base_dir)
            diagnostics_html.append((diagnostic_severity(diagnostic), diagnostic_html))
    return f'<div class="diagnostics">{"".join(d[1] for d in sorted(diagnostics_html, key=itemgetter(0)))}</div>' if \
        diagnostics_html else ''

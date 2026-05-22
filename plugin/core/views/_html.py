from __future__ import annotations

from ..constants import MarkdownLangMap
from ..constants import MARKO_MD_PARSER_VERSION
from ..css import css as lsp_css
from ..settings import userprefs
from functools import lru_cache
from typing import Any
from typing import Callable
from typing import TYPE_CHECKING
import html
import mdpopups
import re
import sublime
import sublime_plugin

if TYPE_CHECKING:
    from ....protocol import MarkedString
    from ....protocol import MarkupContent


FORMAT_STRING = 0x1
FORMAT_MARKED_STRING = 0x2
FORMAT_MARKUP_CONTENT = 0x4


REPLACEMENT_MAP = {
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    "\t": 4 * "&nbsp;",
    "\n": "<br>",
    "\xa0": "&nbsp;",  # non-breaking space
    "\xc2": "&nbsp;",  # control character
}

PATTERNS = [
    r'(?P<special>[{}])'.format(''.join(REPLACEMENT_MAP.keys())),
    r'(?P<url>https?://(?:[\w\d:#@%/;$()~_?\+\-=\\\.&](?:#!)?)*)',
    r'(?P<multispace> {2,})',
]

REPLACEMENT_RE = re.compile('|'.join(PATTERNS), flags=re.IGNORECASE)


def _replace_match(match: Any) -> str:
    special_match = match.group('special')
    if special_match:
        return REPLACEMENT_MAP[special_match]
    if url := match.group('url'):
        return f"<a href='{url}'>{url}</a>"
    return len(match.group('multispace')) * '&nbsp;'


def text2html(content: str) -> str:
    return re.sub(REPLACEMENT_RE, _replace_match, content)


def make_link(href: str, text: Any, class_name: str | None = None, tooltip: str | None = None) -> str:
    link = f"<a href='{href}'"
    if class_name:
        link += f" class='{class_name}'"
    if tooltip:
        link += f" title='{html.escape(tooltip)}'"
    text = text2html(str(text)).replace(' ', '&nbsp;')
    link += f">{text}</a>"
    return link


def make_command_link(
    command: str,
    text: str,
    command_args: dict[str, Any] | None = None,
    class_name: str | None = None,
    tooltip: str | None = None,
    view_id: int | None = None
) -> str:
    if view_id is not None:
        cmd = "lsp_run_text_command_helper"
        args: dict[str, Any] | None = {"view_id": view_id, "command": command, "args": command_args}
    else:
        cmd = command
        args = command_args
    return make_link(sublime.command_url(cmd, args), text, class_name, tooltip)


class LspRunTextCommandHelperCommand(sublime_plugin.WindowCommand):

    def run(self, view_id: int, command: str, args: dict[str, Any] | None = None) -> None:
        view = sublime.View(view_id)
        if view.is_valid():
            view.run_command(command, args)


def _html_element(tag: str, content: str, *, class_name: str | None = None, escape: bool = True) -> str:
    return '<{0}{2}>{1}</{0}>'.format(
        tag,
        text2html(content) if escape else content,
        f' class="{text2html(class_name)}"' if class_name else ''
    )


def html_wrapper(content: str, *, class_name: str | None = None) -> str:
    """
    Wrap content in a container with default pading applied.

    Automatically inserted spacer element acts as a bottom padding to workaround minihtml's margin collapsing bug.
    Otherwise if the last element had bottom margin (for example a paragraph), it would render a double margin.
    The `content` is NOT escaped.
    """
    extra_class = f' {class_name}' if class_name else ''
    return _html_element(
        'div', f'{content}<div class="wrapper--spacer"></div>', class_name=f'wrapper{extra_class}', escape=False)


def show_lsp_popup(
    view: sublime.View,
    contents: str,
    *,
    location: int = -1,
    md: bool = False,
    flags: sublime.PopupFlags = sublime.PopupFlags.NONE,
    css: str | None = None,
    wrapper_class: str | None = None,
    body_id: str | None = None,
    on_navigate: Callable[..., None] | None = None,
    on_hide: Callable[..., None] | None = None
) -> None:
    css = css if css is not None else lsp_css().popups
    wrapper_class = wrapper_class if wrapper_class is not None else lsp_css().popups_classname
    body_wrapper = f'<body id="{body_id}">{{}}</body>' if body_id else '<body>{}</body>'
    mdpopups.show_popup(
        view,
        body_wrapper.format(contents),
        css=css,
        md=md,
        flags=flags,
        location=location,
        wrapper_class=wrapper_class,
        max_width=int(view.em_width() * float(userprefs().popup_max_characters_width)),
        max_height=int(view.line_height() * float(userprefs().popup_max_characters_height)),
        on_navigate=on_navigate,
        on_hide=on_hide)


def update_lsp_popup(
    view: sublime.View,
    contents: str,
    *,
    md: bool = False,
    css: str | None = None,
    wrapper_class: str | None = None,
    body_id: str | None = None
) -> None:
    css = css if css is not None else lsp_css().popups
    wrapper_class = wrapper_class if wrapper_class is not None else lsp_css().popups_classname
    body_wrapper = f'<body id="{body_id}">{{}}</body>' if body_id else '<body>{}</body>'
    mdpopups.update_popup(view, body_wrapper.format(contents), css=css, md=md, wrapper_class=wrapper_class)


def minihtml(
    view: sublime.View,
    content: MarkedString | MarkupContent | list[MarkedString],
    allowed_formats: int,
    language_id_map: MarkdownLangMap | None = None
) -> str:
    """
    Formats provided input content into markup accepted by minihtml.

    Content can be in one of those formats:

     - string: treated as plain text
     - MarkedString: string or { language: string; value: string }
     - MarkedString[]
     - MarkupContent: { kind: MarkupKind, value: string }

    We can't distinguish between plain text string and a MarkedString in a string form so
    FORMAT_STRING and FORMAT_MARKED_STRING can't both be specified at the same time.

    :param view
    :param content
    :param allowed_formats: Bitwise flag specifying which formats to parse.

    :returns: Formatted string
    """
    if allowed_formats == 0:
        raise ValueError("Must specify at least one format")
    parse_string = bool(allowed_formats & FORMAT_STRING)
    parse_marked_string = bool(allowed_formats & FORMAT_MARKED_STRING)
    parse_markup_content = bool(allowed_formats & FORMAT_MARKUP_CONTENT)
    if parse_string and parse_marked_string:
        raise ValueError("Not allowed to specify FORMAT_STRING and FORMAT_MARKED_STRING at the same time")
    is_plain_text = True
    result = ''
    if (parse_string or parse_marked_string) and isinstance(content, str):
        # plain text string or MarkedString
        is_plain_text = parse_string
        result = content
    if parse_marked_string and isinstance(content, list):
        # MarkedString[]
        formatted = []
        for item in content:
            value = ""
            language = None
            if isinstance(item, str):
                value = item
            else:
                value = item.get("value") or ""
                language = item.get("language")

            if language:
                formatted.append(f"```{language}\n{value}\n```\n")
            else:
                formatted.append(value)

        is_plain_text = False
        result = "\n".join(formatted)
    if (parse_marked_string or parse_markup_content) and isinstance(content, dict):
        # MarkupContent or MarkedString (dict)
        language = content.get("language")
        kind = content.get("kind")
        value = content.get("value") or ""
        if parse_markup_content and kind:
            # MarkupContent
            is_plain_text = kind != "markdown"
            result = value
        if parse_marked_string and language:
            # MarkedString (dict)
            is_plain_text = False
            result = f"```{language}\n{value}\n```\n"
    if is_plain_text:
        return f"<span>{text2html(result)}</span>" if result else ''
    frontmatter: dict[str, Any] = {
        "allow_code_wrap": True,
    }
    if MARKO_MD_PARSER_VERSION:
        frontmatter["markdown_parser"] = "marko"
        frontmatter["markdown_extensions"] = ["gfm"]
    else:
        frontmatter["markdown_extensions"] = [
            "markdown.extensions.admonition",
            {
                "pymdownx.magiclink": {
                    # links are displayed without the initial ftp://, http://, https://, or ftps://.
                    "hide_protocol": True,
                    # GitHub, Bitbucket, and GitLab commit, pull, and issue links are are rendered in a shorthand
                    # syntax.
                    "repo_url_shortener": True
                }
            }
        ]
        # Workaround CommonMark deficiency: two spaces followed by a newline should result in a new paragraph.
        result = re.sub('(\\S)  \n', '\\1\n\n', result)  # noqa: RUF039
    if isinstance(language_id_map, dict):
        frontmatter["language_map"] = language_id_map
    return mdpopups.md2html(view, mdpopups.format_frontmatter(frontmatter) + result)


@lru_cache
def lightbulb_html(color: str, star: bool) -> str:
    if star:
        img = 'Packages/LSP/icons/lightbulb-star-32.png'
        tooltip = 'Preferred Quick Fix'
    else:
        img = 'Packages/LSP/icons/lightbulb-32.png'
        tooltip = 'Quick Fix'
    return f'<span class="lightbulb" title="{tooltip}">{mdpopups.tint(img, color)}</span>'

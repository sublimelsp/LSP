from .core.protocol import InlayHintLabelPart, MarkupContent, Point, InlayHint
from .core.typing import List, Optional, Union
from .core.views import FORMAT_MARKUP_CONTENT, point_to_offset, minihtml
import html
import sublime

INLAY_HINT_HTML = """
<body id="lsp-inlay-hint">
    <style>
        .inlay-hint {{
            color: color(var(--foreground) alpha(0.6));
            background-color: color(var(--foreground) alpha(0.08));
            border-radius: 4px;
            margin-left: {margin_left};
            margin-right: {margin_right};
            padding: 0.05em 4px;
            font-size: 0.9em;
            font-family: system;
        }}
    </style>
    <div class="inlay-hint" title="{tooltip}">
        {label}
    </div>
</body>
"""


def format_inlay_hint_tooltip(view: sublime.View, tooltip: Optional[Union[str, MarkupContent]]) -> str:
    if isinstance(tooltip, str):
        return html.escape(tooltip)
    elif isinstance(tooltip, dict):  # MarkupContent
        return minihtml(view, tooltip, allowed_formats=FORMAT_MARKUP_CONTENT)
    else:
        return ""


def format_inlay_hint_label(view: sublime.View, label: Union[str, List[InlayHintLabelPart]]) -> str:
    if isinstance(label, str):
        return html.escape(label)
    else:
        return "".join("<div title=\"{tooltip}\">{value}</div>".format(
            tooltip=format_inlay_hint_tooltip(view, label_part.get("tooltip")),
            value=label_part.get("value")
        ) for label_part in label)


def inlay_hint_to_phantom(view: sublime.View, inlay_hint: InlayHint) -> sublime.Phantom:
    region = sublime.Region(point_to_offset(Point.from_lsp(inlay_hint["position"]), view))
    tooltip = format_inlay_hint_tooltip(view, inlay_hint.get("tooltip"))
    label = format_inlay_hint_label(view, inlay_hint["label"])
    margin_left = "0.6rem" if inlay_hint.get("paddingLeft", False) else "0"
    margin_right = "0.6rem" if inlay_hint.get("paddingRight", False) else "0"
    content = INLAY_HINT_HTML.format(
        margin_left=margin_left,
        margin_right=margin_right,
        tooltip=tooltip,
        label=label)
    return sublime.Phantom(region, content, sublime.LAYOUT_INLINE)

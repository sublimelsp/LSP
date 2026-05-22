from __future__ import annotations

from ._coordinates import range_to_region
from typing import TYPE_CHECKING
import sublime

if TYPE_CHECKING:
    from ....protocol import Color
    from ....protocol import ColorInformation

COLOR_BOX_HTML = """
<style>
    html {{
        padding: 0;
        background-color: transparent;
    }}
    a {{
        display: inline-block;
        height: 0.8rem;
        width: 0.8rem;
        margin-top: 0.1em;
        border: 1px solid color(var(--foreground) alpha(0.25));
        background-color: {color};
        text-decoration: none;
    }}
</style>
<body id='lsp-color-box'>
    <a href='{command}'>&nbsp;</a>
</body>"""


def color_to_hex(color: Color) -> str:
    red = round(color['red'] * 255)
    green = round(color['green'] * 255)
    blue = round(color['blue'] * 255)
    alpha_dec = color['alpha']
    if alpha_dec < 1:
        return f"#{red:02x}{green:02x}{blue:02x}{round(alpha_dec * 255):02x}"
    return f"#{red:02x}{green:02x}{blue:02x}"


def lsp_color_to_html(color_info: ColorInformation) -> str:
    command = sublime.command_url('lsp_color_presentation', {'color_information': color_info})
    return COLOR_BOX_HTML.format(command=command, color=color_to_hex(color_info['color']))


def lsp_color_to_phantom(view: sublime.View, color_info: ColorInformation) -> sublime.Phantom:
    region = range_to_region(color_info['range'], view)
    return sublime.Phantom(region, lsp_color_to_html(color_info), sublime.PhantomLayout.INLINE)

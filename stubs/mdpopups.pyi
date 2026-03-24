from typing import Any
from typing import Callable
import sublime


def version() -> tuple[int, int, int]:
    """
    Returns the version of the MdPopups library. Returns a tuple of integers which represents the major, minor, and
    patch version.
    """
    ...


def show_popup(
    view: sublime.View,
    content: str,
    md: bool = ...,
    css: str | None = ...,
    flags: int = ...,
    location: int = ...,
    max_width: int = ...,
    max_height: int = ...,
    on_navigate: Callable[[str], None] | None = ...,
    on_hide: Callable[[str], None] | None = ...,
    wrapper_class: str | None = ...,
    template_vars: dict[str, Any] | None = ...,
    template_env_options: dict[str, Any] | None = ...
) -> None:
    """
    Accepts Markdown and creates a Sublime popup. By default, the built-in Sublime syntax highlighter will be used for
    code highlighting.
    """
    ...


def update_popup(
    view: sublime.View,
    content: str,
    md: bool = ...,
    css: str | None = ...,
    wrapper_class: str | None = ...,
    template_vars: dict[str, Any] | None = ...,
    template_env_options: dict[str, Any] | None = ...
) -> None:
    """
    Updates the current existing popup.
    """
    ...


def hide_popup(view: sublime.View) -> None:
    """
    Hides the current popup. Included for convenience and consistency.
    """
    ...


def is_popup_visible(view: sublime.View) -> bool:
    """
    Checks if popup is visible in the view. Included for convenience and consistency.
    """
    ...


def add_phantom(
    view: sublime.View,
    key: str,
    region: sublime.Region,
    content: str,
    layout: sublime.PhantomLayout,
    md: bool = ...,
    css: str | None = ...,
    on_navigate: Callable[[str], None] | None = ...,
    wrapper_class: str | None = ...,
    template_vars: dict[str, Any] | None = ...,
    template_env_options: dict[str, Any] | None = ...
) -> int:
    """
    Adds a phantom to the view and returns the phantom id as an integer. By default, the built-in Sublime syntax
    highlighter will be used for code highlighting.
    """
    ...


def erase_phantoms(view: sublime.View, key: str) -> None:
    """
    Erase all phantoms associated with the given key. Included for convenience and consistency.
    """
    ...


def erase_phantom_by_id(view: sublime.View, pid: str) -> None:
    """
    Erase a single phantom by its id. Included for convenience and consistency.
    """
    ...


def query_phantom(view: sublime.View, pid: int) -> list[sublime.Region]:
    """
    Query the location of a phantom by specifying its id. A list of `sublime.Region`s will be returned. If the phantom
    with the given id is not found, the region will be returned with positions of `(-1, -1)`. Included for convenience
    and consistency.
    """
    ...


def query_phantoms(view: sublime.View, pids: list[int]) -> list[sublime.Region]:
    """
    Query the location of multiple phantoms by specifying their ids. A list of `sublime.Region`s will be returned where
    each index corresponds to the index of ids that was passed in. If a given phantom id is not found, that region will
    be returned with positions of `(-1, -1)`. Included for convenience and consistency.
    """
    ...


class Phantom:
    """
    A phantom object for use with `PhantomSet`.
    """
    region: sublime.Region
    content: str
    layout: sublime.PhantomLayout
    md: bool
    css: str | None
    on_navigate: Callable[[str], None] | None
    wrapper_class: str | None
    template_vars: dict[str, Any] | None
    template_env_options: dict[str, Any] | None

    def __init__(
        self,
        region: sublime.Region,
        content: str,
        layout: sublime.PhantomLayout,
        md: bool = ...,
        css: str | None = ...,
        on_navigate: Callable[[str], None] | None = ...,
        wrapper_class: str | None = ...,
        template_vars: dict[str, Any] | None = ...,
        template_env_options: dict[str, Any] | None = ...
    ) -> None:
        ...

    def __eq__(self, rhs: object) -> bool:
        ...


class PhantomSet:
    """
    A class that allows you to update phantoms under the specified key.
    """

    def __init__(self, view: sublime.View, key: str) -> None:
        ...

    def update(self, new_phantoms: list[Phantom]) -> None:
        ...


def new_html_sheet(
    window: sublime.Window,
    name: str,
    contents: str,
    md: bool = ...,
    css: str | None = ...,
    flags: sublime.NewFileFlags = ...,
    group: int = ...,
    wrapper_class: str | None = ...,
    template_vars: dict[str, Any] | None = ...,
    template_env_options: dict[str, Any] | None = ...
) -> sublime.HtmlSheet:
    """
    Accepts Markdown and creates a Sublime HTML sheet. By default, the built-in Sublime syntax highlighter will be used
    for code highlighting.
    """
    ...


def update_html_sheet(
    sheet: sublime.HtmlSheet,
    contents: str,
    md: bool = ...,
    css: str | None = ...,
    wrapper_class: str | None = ...,
    template_vars: dict[str, Any] | None = ...,
    template_env_options: dict[str, Any] | None = ...
) -> None:
    """
    Accepts Markdown and updates the content of a Sublime HTML sheet. By default, the built-in Sublime syntax
    highlighter will be used for code highlighting.
    """
    ...


def clear_cache() -> None:
    """
    Clears the CSS theme related caches.
    """
    ...


def md2html(
    view: sublime.View,
    markup: str,
    template_vars: dict[str, Any] | None = ...,
    template_env_options: dict[str, Any] | None = ...
) -> str:
    """
    Exposes the Markdown to HTML converter in case it is desired to parse only a section of markdown. This works well
    for someone who wants to work directly in HTML, but might want to still have fragments of markdown that they would
    like to occasionally convert. By default, the built-in Sublime syntax highlighter will be used for code
    highlighting.
    """
    ...


def color_box(
    colors: list[str],
    border: str = ...,
    border2: str | None = ...,
    height: int = ...,
    width: int = ...,
    border_size: int = ...,
    check_size: int = ...,
    max_colors: int = ...,
    alpha: bool = ...,
    border_map: int = ...
) -> str:
    """
    Generates a color preview box image encoded in base 64 and formatted to be inserted right in your your Markdown or
    HTML code as an `img` tag.
    """
    ...


def color_box_raw(
    colors: list[str],
    border: str = ...,
    border2: str | None = ...,
    height: int = ...,
    width: int = ...,
    border_size: int = ...,
    check_size: int = ...,
    max_colors: int = ...,
    alpha: bool = ...,
    border_map: int = ...
) -> bytes:
    """
    Generates a color preview box image and returns the raw byte string of the image.
    """
    ...


def tint(img: str | bytes, color: str, opacity: int = ..., height: int = ..., width: int = ...) -> str:
    """
    Takes a either a path to an PNG or a byte string of a PNG and tints it with a specific color and returns a string
    containing the base 64 encoded PNG in a HTML element.
    """
    ...


def tint_raw(img: str | bytes, color: str, opacity: int = ...) -> bytes:
    """
    Takes a either a path to an PNG or a byte string of a PNG and tints it with a specific color and returns a byte
    string of the modified PNG.
    """
    ...


def scope2style(
    view: sublime.View, scope: str, selected: bool = ..., explicit_background: bool = ...
) -> dict[str, Any]:
    """
    Takes a sublime scope (complexity doesn't matter), and guesses the style that would be applied. While there may be
    untested corner cases with complex scopes where it fails, in general, it is usually accurate.
    """
    ...


def syntax_highlight(
    view: sublime.View,
    src: str,
    language: str | None = ...,
    inline: bool = ...,
    allow_code_wrap: bool = ...,
    language_map: dict[str, list[list[str]]] | None = ...
) -> str:
    """
    Allows for syntax highlighting outside the Markdown environment. You can just feed it code directly and give it the
    language of your choice, and you will be returned a block of HTML that has been syntax highlighted. By default, the
    built-in Sublime syntax highlighter will be used for code highlighting.
    """
    ...


def tabs2spaces(text: str, tab_size: int = ...) -> str:
    """
    The Markdown parser used converts all tabs to spaces with the simple logic of 1 tab equals 4 spaces. This logic is
    generally applied in other places like `syntax_highlight`. When formatting code for `syntax_highlight`, you may want
    to translate the tabs to spaces based on tab stops before passing it through opposed to apply the simple logic of
    converting all tabs to 4 spaces regardless of tab stops. `tabs2spaces` does exactly this, allowing you format the
    whitespace in a more intelligent manner.

    `tabs2spaces` cannot do anything about characters, and there are some even in monospace fonts, that are wider than
    normal characters. It doesn't detect zero width characters either. It also cannot predict cases where two or more
    Unicode character are shown as one. But in some cases, this more intelligent output is much better than the "all
    tabs are arbitrarily one size" logic.
    """
    ...


def get_language_from_view(view: sublime.View) -> str | None:
    """
    Allows a user to extract the equivalent language specifier for `mdpopups.syntax_highlight` from a view. If the
    language cannot be determined, `None` will be returned.
    """
    ...


def resolve_images(
    minihtml: str, resolver: Callable[[str, Callable[[bytes], None]], None], on_done: Callable[[str], None]
) -> object | None:
    """
    This was added to download remote images. `resolve_images` accepts an HTML buffer, a resolver and a callback and
    will search the HTML buffer for image URLs and download them if appropriate.

    Since this function can have a resolver that can download the images asynchronously, it is not performed in the main
    path when showing popups or phantoms.

    Ideally, this would be used after manually running Markdown through `md2html`.
    """
    ...


def blocking_resolver(url: str, done: Callable[[bytes], None]) -> None:
    """
    A blocking image resolver. Will block while download an image.
    """
    ...


def ui_thread_resolver(url: str, done: Callable[[bytes], None]) -> None:
    """
    Will execute image downloads on the main thread.
    """
    ...


def worker_thread_resolver(url: str, done: Callable[[bytes], None]) -> None:
    """
    Will execute image downloads on the worker ("async") thread of Sublime Text.
    """
    ...


def format_frontmatter(values: dict[str, Any]) -> str:
    """
    Format values as frontmatter.
    """
    ...

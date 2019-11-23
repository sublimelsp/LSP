import sublime
try:
    from typing import Callable, Optional
    assert Callable and Optional
except ImportError:
    pass


def show_popup(
    view: sublime.View,
    content: str,
    md: bool = True,
    css=None,  # type: Optional[str]
    flags: int = 0,
    location: int = -1,
    max_width: int = 320,
    max_height: int = 240,
    on_navigate=None,  # type: Optional[Callable]
    on_hide=None,  # type: Optional[Callable]
    wrapper_class=None,  # type: Optional[str]
    template_vars=None,  # type: Optional[dict]
    template_env_options=None,  # type: Optional[dict]
    nl2br: bool = True,
    allow_code_wrap: bool = False
) -> None: ...


def update_popup(
    view: sublime.View,
    content: str,
    md: bool = True,
    css=None,  # type: Optional[str]
    wrapper_class=None,  # type: Optional[str]
    template_vars=None,  # type: Optional[str]
    nl2br: bool = True,
    allow_code_wrap: bool = False
) -> None: ...


def md2html(
    view: sublime.View,
    content: str,
    template_vars=None,  # type: Optional[str]
    template_env_options=None,  # type: Optional[dict]
    nl2br: bool = True,
    allow_code_wrap: bool = False
) -> str: ...


def scope2style(
    view: sublime.View,
    scope: str,
    selected: bool = False,
    explicit_background: bool = False
) -> str: ...

import sublime
try:
    from typing import Callable, Optional
    assert Callable and Optional
except ImportError:
    pass


def show_popup(
    view: sublime.View,
    content: str,
    md=True,
    css=None,  # type: Optional[str]
    flags=0,
    location=-1,
    max_width=320,
    max_height=240,
    on_navigate=None,  # type: Optional[Callable]
    on_hide=None,  # type: Optional[Callable]
    wrapper_class=None,  # type: Optional[str]
    template_vars=None,  # type: Optional[dict]
    template_env_options=None,  # type: Optional[dict]
    nl2br=True,
    allow_code_wrap=False
): ...

def update_popup(
    view: sublime.View,
    content: str,
    md=True,
    css=None,  # type: Optional[str]
    wrapper_class=None,  # type: Optional[str]
    template_vars=None,  # type: Optional[str]
    nl2br=True,
    allow_code_wrap=False
): ...


def md2html(
    view: sublime.View,
    content: str,
    template_vars=None,  # type: Optional[str]
    template_env_options=None,  # type: Optional[dict]
    nl2br=True,
    allow_code_wrap=False
): ...
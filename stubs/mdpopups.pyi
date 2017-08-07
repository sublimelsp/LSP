import sublime

def show_popup(
    view: sublime.View,
    content: str,
    md=True,
    css=None,
    flags=0,
    location=-1,
    max_width=320,
    max_height=240,
    on_navigate=None,
    on_hide=None,
    wrapper_class=None,
    template_vars=None,
    template_env_options=None,
    nl2br=True,
    allow_code_wrap=False
): ...

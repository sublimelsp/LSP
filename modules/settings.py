import sublime

try:
    from typing import Set
    assert Set
except ImportError:
    pass


class ClientConfig(object):

    def __init__(self, name, data):
        self.name = name
        self.command = data.get("command") or []
        self.scopes = set(data.get("scopes") or [])
        self.syntaxes = set(data.get("syntaxes") or [])
        self.languageId = data.get("languageId") or ""

    def __hash__(self):
        return hash(self.name)


class LSPSettings(object):

    # template of handled settings and their failsafe defaults.
    lookup = {
        "show_status_messages": True,
        "show_view_status": True,
        "auto_show_diagnostics_panel": True,
        "show_diagnostics_phantoms": True,
        "show_diagnostics_in_view_status": True,
        "log_debug": False,
        "log_server": True,
        "log_stderr": False
    }

    def __init__(self):
        self.clients = set()    # type: Set
        self.settings = None    # type: sublime.Settings
        # initialize defaults until self.load() is called
        for key, default in self.lookup.items():
            self.__setattr__(key, default)

    def __del__(self):
        if self.settings:
            self.settings.clear_on_change("LSP.update")

    def load(self):
        if not self.settings:
            self.settings = sublime.load_settings("LSP.sublime-settings")
            self.settings.add_on_change("LSP.update", lambda: self.update())
        self.update()

    def update(self):
        """Update class attributes from sublime.Settings object."""
        print("LSP: reloading settings")
        for key, default in self.lookup.items():
            self.__setattr__(key, self.settings.get(key, default))
        self.clients.clear()
        client_configs = self.settings.get("clients", {})
        for client_name, client_config in client_configs.items():
            self.clients.add(ClientConfig(client_name, client_config))


lsp_settings = LSPSettings()

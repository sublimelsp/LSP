import sublime


class PopupsConfig(object):

    def __init__(self) -> None:
        self.classname = "lsp_popup"
        self.stylesheet = ""

    def load_css(self) -> None:
        self.stylesheet = sublime.load_resource("Packages/LSP/popups.css")


popups = PopupsConfig()

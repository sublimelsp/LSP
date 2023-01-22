import sublime
import sublime_plugin


class LspDoubleClick(sublime_plugin.TextCommand):
    def __init__(self, view: sublime.View) -> None:
        super().__init__(view)
        self.click_count = 0

    def run(self, edit: sublime.Edit, command: str, args: dict) -> None:
        self.click_count += 1
        if (self.click_count == 2):
            self.view.run_command(command, args)
            self.click_count = 0
            return
        def reset() -> None:
            self.click_count = 0
        sublime.set_timeout(reset, 500)

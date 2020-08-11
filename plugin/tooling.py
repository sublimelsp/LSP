import sublime
import sublime_plugin
import json
import textwrap
from .core.typing import Optional


class LspParseVscodePackageJson(sublime_plugin.ApplicationCommand):

    def __init__(self) -> None:
        self.view = None  # type: Optional[sublime.View]

    def writeline(self, contents: str, indent: int = 0) -> None:
        if self.view is not None:
            self.view.run_command("append", {"characters": " " * indent + contents + "\n"})

    def writeline4(self, contents: str) -> None:
        self.writeline(contents, indent=4)

    def run(self) -> None:
        package = json.loads(sublime.get_clipboard())
        contributes = package.get("contributes")
        if not isinstance(contributes, dict):
            sublime.error_message('No "contributes" key found!')
            return
        configuration = contributes.get("configuration")
        if not isinstance(configuration, dict):
            sublime.error_message('No "contributes.configuration" key found!')
            return
        properties = configuration.get("properties")
        if not isinstance(properties, dict):
            sublime.error_message('No "contributes.configuration.properties" key found!')
            return
        self.view = sublime.active_window().new_file()
        self.view.set_scratch(True)
        self.view.set_name("--- PARSED SETTINGS ---")
        self.view.assign_syntax("Packages/JSON/JSON.sublime-syntax")
        self.writeline("{")
        # schema = {}  TODO: Also generate a schema. Sublime settings are not rigid.
        for k, v in sorted(properties.items()):
            typ = v["type"]
            description = v.get("description")
            if isinstance(description, str):
                for line in description.splitlines():
                    for wrapped_line in textwrap.wrap(line, width=73):
                        self.writeline4('// {}'.format(wrapped_line))
            else:
                self.writeline4('// unknown setting')
            enum = v.get("enum")
            has_default = "default" in v
            default = v.get("default")
            if isinstance(enum, list):
                self.writeline4('// possible values: {}'.format(", ".join(enum)))
            if has_default:
                value = default
            else:
                self.writeline4('// NO DEFAULT VALUE <-- NEEDS ATTENTION')
                if typ == "string":
                    value = ""
                elif typ == "boolean":
                    value = False
                elif typ == "array":
                    value = []
                elif typ == "object":
                    value = {}
                elif typ == "number":
                    value = 0
                else:
                    self.writeline4('// UNKNOWN TYPE: {} <-- NEEDS ATTENTION'.format(typ))
                    value = ""
            value_lines = json.dumps(value, ensure_ascii=False, indent=4).splitlines()
            for index, line in enumerate(value_lines, 1):
                is_last_line = index == len(value_lines)
                terminator = ',' if is_last_line else ''
                if index == 1:
                    self.writeline4('"{}": {}{}'.format(k, line, terminator))
                else:
                    self.writeline4('{}{}'.format(line, terminator))
        self.writeline("}")

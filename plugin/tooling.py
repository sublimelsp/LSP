from .core.css import css
from .core.registry import windows
from .core.transports import create_transport
from .core.transports import Transport
from .core.transports import TransportCallbacks
from .core.types import ClientConfig
from .core.typing import Any, Callable, Dict, List, Optional
from .core.version import __version__
from .core.views import extract_variables
from .core.views import make_command_link
from base64 import b64decode
from base64 import b64encode
from subprocess import list2cmdline
import json
import mdpopups
import os
import sublime
import sublime_plugin
import textwrap


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


class LspTroubleshootServerCommand(sublime_plugin.WindowCommand, TransportCallbacks):

    def run(self) -> None:
        window = self.window
        active_view = window.active_view()
        configs = [c for c in windows.lookup(window).get_config_manager().get_configs() if c.enabled]
        config_names = [config.name for config in configs]
        if config_names:
            window.show_quick_panel(config_names, lambda index: self.on_selected(index, configs, active_view),
                                    placeholder='Select server to troubleshoot')

    def on_selected(self, selected_index: int, configs: List[ClientConfig],
                    active_view: Optional[sublime.View]) -> None:
        if selected_index == -1:
            return
        config = configs[selected_index]
        output_sheet = mdpopups.new_html_sheet(
            self.window, 'Server: {}'.format(config.name), '# Running server test...',
            css=css().sheets, wrapper_class=css().sheets_classname)
        sublime.set_timeout_async(lambda: self.test_run_server_async(config, self.window, active_view, output_sheet))

    def test_run_server_async(self, config: ClientConfig, window: sublime.Window,
                              active_view: Optional[sublime.View], output_sheet: sublime.HtmlSheet) -> None:
        server = ServerTestRunner(
            config, window,
            lambda output, exit_code: self.update_sheet(config, active_view, output_sheet, output, exit_code))
        # Store the instance so that it's not GC'ed before it's finished.
        self.test_runner = server  # type: Optional[ServerTestRunner]

    def update_sheet(self, config: ClientConfig, active_view: Optional[sublime.View], output_sheet: sublime.HtmlSheet,
                     server_output: str, exit_code: int) -> None:
        self.test_runner = None
        frontmatter = mdpopups.format_frontmatter({'allow_code_wrap': True})
        contents = self.get_contents(config, active_view, server_output, exit_code)
        # The href needs to be encoded to avoid having markdown parser ruin it.
        copy_link = make_command_link('lsp_copy_to_clipboard_from_base64', '<kbd>Copy to clipboard</kbd>',
                                      {'contents': b64encode(contents.encode()).decode()})
        formatted = '{}{}\n{}'.format(frontmatter, copy_link, contents)
        mdpopups.update_html_sheet(output_sheet, formatted, css=css().sheets, wrapper_class=css().sheets_classname)

    def get_contents(self, config: ClientConfig, active_view: Optional[sublime.View],
                     server_output: str, exit_code: int) -> str:
        lines = []

        def l(s: str) -> None:
            lines.append(s)

        l('# Troubleshooting: {}'.format(config.name))

        l('## Version')
        l(' - LSP: {}'.format('.'.join([str(n) for n in __version__])))
        l(' - Sublime Text: {}'.format(sublime.version()))

        l('## System PATH')
        lines += [' - {}'.format(p) for p in os.environ['PATH'].split(os.pathsep)]

        l('## Server Test Run')
        l(' - exit code: {}\n - output\n```\n{}\n```'.format(exit_code, server_output))

        l('## Server Configuration')
        l(' - command\n```js\n{}\n```'.format(config.binary_args))
        l(' - shell command\n```sh\n{}\n```'.format(list2cmdline(config.binary_args)))
        l(' - languages')
        languages = [
            {
                'language_id': lang.id,
                'document_selector': lang.document_selector,
                'feature_selector': lang.feature_selector,
            } for lang in config.languages
        ]
        l('```js\n{}\n```'.format(self.json_dump(languages)))
        l(' - init_options')
        l('```js\n{}\n```'.format(self.json_dump(config.init_options)))
        l(' - settings')
        l('```js\n{}\n```'.format(self.json_dump(config.settings.get())))
        l(' - env')
        l('```\n{}\n```'.format(self.json_dump(config.env)))

        l('\n## Active view')
        if active_view:
            l(' - File name\n```\n{}\n```'.format(active_view.file_name()))
            l(' - Settings')
            keys = ['auto_complete_selector', 'lsp_active', 'syntax']
            settings = {}
            view_settings = active_view.settings()
            for key in keys:
                settings[key] = view_settings.get(key)
            l('```js\n{}\n```'.format(self.json_dump(settings)))
        else:
            l('no active view found!')

        window = self.window
        l('\n## Project / Workspace')
        l(' - folders')
        l('```js\n{}\n```'.format(window.folders()))
        is_project = bool(window.project_file_name())
        l(' - is project: {}'.format(is_project))
        if is_project:
            l(' - project data:\n```js\n{}\n```'.format(self.json_dump(window.project_data())))

        l('\n## LSP configuration\n')
        lsp_settings = self.read_resource('Packages/User/LSP.sublime-settings')
        l('```js\n{}\n```'.format(lsp_settings) if lsp_settings else 'no LSP settings')

        return '\n'.join(lines)


    def json_dump(self, contents: Any) -> str:
        return json.dumps(contents, indent=2, sort_keys=True, ensure_ascii=False)

    def read_resource(self, path: str) -> Optional[str]:
        try:
            return sublime.load_resource(path)
        except Exception:
            return None


class LspCopyToClipboardFromBase64Command(sublime_plugin.ApplicationCommand):
    def run(self, contents: str) -> None:
        sublime.set_clipboard(b64decode(contents).decode())


class ServerTestRunner(TransportCallbacks):
    """
    Used to start the server and collect any potential stderr output and the exit code.

    Server is automatically closed after defined timeout.
    """

    CLOSE_TIMEOUT_SEC = 2

    def __init__(self, config: ClientConfig, window: sublime.Window, on_close: Callable[[str, int], None]) -> None:
        self._on_close = on_close  # type: Callable[[str, int], None]
        self._transport = None  # type: Optional[Transport]
        self._stderr_lines = []  # type: List[str]
        try:
            cwd = window.folders()[0] if window.folders() else None
            variables = extract_variables(window)
            self._transport = create_transport(config, cwd, window, self, variables)
            sublime.set_timeout_async(self.force_close_transport, self.CLOSE_TIMEOUT_SEC * 1000)
        except Exception as ex:
            self.on_transport_close(-1, ex)

    def force_close_transport(self) -> None:
        if self._transport:
            self._transport.close()

    def on_payload(self, payload: Dict[str, Any]) -> None:
        pass

    def on_stderr_message(self, message: str) -> None:
        self._stderr_lines.append(message)

    def on_transport_close(self, exit_code: int, exception: Optional[Exception]) -> None:
        self._transport = None
        output = str(exception) if exception else '\n'.join(self._stderr_lines).rstrip()
        sublime.set_timeout(lambda: self._on_close(output, exit_code))

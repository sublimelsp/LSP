from .core.css import css
from .core.registry import windows
from .core.sessions import get_plugin
from .core.transports import create_transport
from .core.transports import Transport
from .core.transports import TransportCallbacks
from .core.types import Capabilities
from .core.types import ClientConfig
from .core.typing import Any, Callable, Dict, List, Optional, Tuple
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
import urllib.parse
import urllib.request


def _translate_description(translations: Optional[Dict[str, str]], descr: str) -> Tuple[str, bool]:
    """
    Translate a placeholder description like "%foo.bar.baz" into an English translation. The translation map is
    the first argument.
    """
    if translations and descr.startswith("%") and descr.endswith("%") and len(descr) > 2:
        translated = translations.get(descr.strip("%"))
        if isinstance(translated, str):
            return translated, True
    return descr, False


def _preprocess_properties(translations: Optional[Dict[str, str]], properties: Dict[str, Any]) -> None:
    """
    Preprocess the server settings from a package.json file:

    - Replace description translation placeholders by their English translation
    - Discard the "scope" key
    """
    for v in properties.values():
        v.pop("scope", None)
        descr = v.get("description")
        if not isinstance(descr, str):
            descr = v.get("markdownDescription")
        if isinstance(descr, str):
            descr, translated = _translate_description(translations, descr)
            if translated:
                if "markdownDescription" in v:
                    v["markdownDescription"] = descr
                elif "description" in v:
                    v["description"] = descr
        enums = v.get("enumDescriptions")
        if not isinstance(enums, list):
            enums = v.get("markdownEnumDescriptions")
        if isinstance(enums, list):
            new_enums = []  # type: List[str]
            for descr in enums:
                descr, _ = _translate_description(translations, descr)
                new_enums.append(descr)
            if "enumDescriptions" in v:
                v["enumDescriptions"] = new_enums
            elif "markdownEnumDescriptions" in v:
                v["markdownEnumDescriptions"] = new_enums
        child_properties = v.get("properties")
        if isinstance(child_properties, dict):
            _preprocess_properties(translations, child_properties)


class BasePackageNameInputHandler(sublime_plugin.TextInputHandler):

    def initial_text(self) -> str:
        return "foobar"

    def preview(self, text: str) -> str:
        return "Suggested resource location: Packages/LSP-{0}/LSP-{0}.sublime-settings".format(text)


class LspParseVscodePackageJson(sublime_plugin.ApplicationCommand):

    def __init__(self) -> None:
        self.view = None  # type: Optional[sublime.View]

    def writeline(self, contents: str, indent: int = 0) -> None:
        if self.view is not None:
            self.view.run_command("append", {"characters": " " * indent + contents + "\n"})

    def writeline4(self, contents: str) -> None:
        self.writeline(contents, indent=4)

    def input(self, args: Dict[str, Any]) -> Optional[sublime_plugin.CommandInputHandler]:
        if "base_package_name" not in args:
            return BasePackageNameInputHandler()
        return None

    def run(self, base_package_name: str) -> None:
        # Download the contents of the URL pointing to the package.json file.
        base_url = sublime.get_clipboard()
        try:
            urllib.parse.urlparse(base_url)
        except Exception:
            sublime.error_message("The clipboard content must be a URL to a package.json file.")
            return
        if not base_url.endswith("package.json"):
            sublime.error_message("URL must end with 'package.json'")
            return
        try:
            package = json.loads(urllib.request.urlopen(base_url).read().decode("utf-8"))
        except Exception as ex:
            sublime.error_message('Unable to load "{}": {}'.format(base_url, ex))
            return

        # There might be a translations file as well.
        translations_url = base_url[:-len("package.json")] + "package.nls.json"
        try:
            translations = json.loads(urllib.request.urlopen(translations_url).read().decode("utf-8"))
        except Exception:
            translations = None

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

        # Process each key-value pair of the server settings.
        # If a translations file was found, then we replace the translation key with the English translation.
        _preprocess_properties(translations, properties)

        # We fill a scratch buffer where we create a proposed dictionary of key-value pairs to be used in an
        # LSP-foobar.sublime-settings file, under a "settings" key.
        self.view = sublime.active_window().new_file()
        self.view.set_scratch(True)
        self.view.set_name("--- Proposed server settings for .sublime-settings file ---")
        self.view.assign_syntax("Packages/JSON/JSON.sublime-syntax")
        self.writeline("{")
        for k, v in sorted(properties.items()):
            description = v.get("description")
            if not isinstance(description, str):
                description = v.get("markdownDescription")
            if isinstance(description, str):
                for line in description.splitlines():
                    for wrapped_line in textwrap.wrap(line, width=80 - 8 - 3):
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
                typ = v.get("type")
                # self.writeline4('// NO DEFAULT VALUE <-- NEEDS ATTENTION')
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
        self.view.set_read_only(True)
        self.view = None

        # Create a scratch buffer for the proposed sublime-package.json file. This is actually easier to do than
        # rendering the server settings for the .sublime-settings file.
        view = sublime.active_window().new_file()
        view.set_scratch(True)
        view.set_name("--- Proposed sublime-package.json ---")
        view.assign_syntax("Packages/JSON/JSON.sublime-syntax")
        sublime_package_json = {
            "contributions": {
                "settings": [
                    {
                        "file_patterns": [
                            "/LSP-{}.sublime-settings".format(base_package_name)
                        ],
                        "schema": {
                            "$id": "sublime://settings/LSP-{}".format(base_package_name),
                            "definitions": {
                                "PluginConfig": {
                                    "properties": {
                                        "settings": {
                                            "additionalProperties": False,
                                            "properties": {k: v for k, v in properties.items()}
                                        }
                                    },
                                },
                            },
                            "allOf": [
                                {
                                    "$ref": "sublime://settings/LSP-plugin-base"
                                },
                                {
                                    "$ref": "sublime://settings/LSP-{}#/definitions/PluginConfig".format(base_package_name)  # noqa: E501
                                }
                            ]
                        }
                    },
                    {
                        "file_patterns": [
                            "/*.sublime-project"
                        ],
                        "schema": {
                            "properties": {
                                "settings": {
                                    "properties": {
                                        "LSP": {
                                            "properties": {
                                                "LSP-{}".format(base_package_name): {
                                                    "$ref": "sublime://settings/LSP-{}#/definitions/PluginConfig".format(base_package_name)  # noqa: E501
                                                }
                                            }
                                        }
                                    }
                                }
                            }
                        }
                    }
                ]
            }}
        view.run_command("append", {"characters": json.dumps(sublime_package_json, indent=2, separators=(",", ": "))})
        view.run_command("append", {"characters": "\n"})
        view.set_read_only(True)


class LspTroubleshootServerCommand(sublime_plugin.WindowCommand, TransportCallbacks):

    def run(self) -> None:
        window = self.window
        active_view = window.active_view()
        configs = windows.lookup(window).get_config_manager().get_configs()
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
            lambda resolved_command, output, exit_code: self.update_sheet(
                config, active_view, output_sheet, resolved_command, output, exit_code))
        # Store the instance so that it's not GC'ed before it's finished.
        self.test_runner = server  # type: Optional[ServerTestRunner]

    def update_sheet(self, config: ClientConfig, active_view: Optional[sublime.View], output_sheet: sublime.HtmlSheet,
                     resolved_command: List[str], server_output: str, exit_code: int) -> None:
        self.test_runner = None
        frontmatter = mdpopups.format_frontmatter({'allow_code_wrap': True})
        contents = self.get_contents(config, active_view, resolved_command, server_output, exit_code)
        # The href needs to be encoded to avoid having markdown parser ruin it.
        copy_link = make_command_link('lsp_copy_to_clipboard_from_base64', '<kbd>Copy to clipboard</kbd>',
                                      {'contents': b64encode(contents.encode()).decode()})
        formatted = '{}{}\n{}'.format(frontmatter, copy_link, contents)
        mdpopups.update_html_sheet(output_sheet, formatted, css=css().sheets, wrapper_class=css().sheets_classname)

    def get_contents(self, config: ClientConfig, active_view: Optional[sublime.View], resolved_command: List[str],
                     server_output: str, exit_code: int) -> str:
        lines = []

        def line(s: str) -> None:
            lines.append(s)

        line('# Troubleshooting: {}'.format(config.name))

        line('## Version')
        line(' - LSP: {}'.format('.'.join([str(n) for n in __version__])))
        line(' - Sublime Text: {}'.format(sublime.version()))

        line('## Server Test Run')
        line(' - exit code: {}\n - output\n{}'.format(exit_code, self.code_block(server_output)))

        line('## Server Configuration')
        line(' - command\n{}'.format(self.json_dump(config.command)))
        line(' - shell command\n{}'.format(self.code_block(list2cmdline(resolved_command), 'sh')))
        line(' - selector\n{}'.format(self.code_block(config.selector)))
        line(' - priority_selector\n{}'.format(self.code_block(config.priority_selector)))
        line(' - init_options')
        line(self.json_dump(config.init_options.get()))
        line(' - settings')
        line(self.json_dump(config.settings.get()))
        line(' - env')
        line(self.json_dump(config.env))

        line('\n## Active view')
        if active_view:
            line(' - File name\n{}'.format(self.code_block(active_view.file_name() or 'None')))
            line(' - Settings')
            keys = ['auto_complete_selector', 'lsp_active', 'syntax']
            settings = {}
            view_settings = active_view.settings()
            for key in keys:
                settings[key] = view_settings.get(key)
            line(self.json_dump(settings))
            if isinstance(settings['syntax'], str):
                syntax = sublime.syntax_from_path(settings['syntax'])
                if syntax:
                    line(' - base scope\n{}'.format(self.code_block(syntax.scope)))
        else:
            line('no active view found!')

        window = self.window
        line('\n## Project / Workspace')
        line(' - folders')
        line(self.json_dump(window.folders()))
        is_project = bool(window.project_file_name())
        line(' - is project: {}'.format(is_project))
        if is_project:
            line(' - project data:\n{}'.format(self.json_dump(window.project_data())))

        line('\n## LSP configuration\n')
        lsp_settings_contents = self.read_resource('Packages/User/LSP.sublime-settings')
        if lsp_settings_contents is not None:
            line(self.json_dump(sublime.decode_value(lsp_settings_contents)))
        else:
            line('<not found>')

        line('## System PATH')
        lines += [' - {}'.format(p) for p in os.environ['PATH'].split(os.pathsep)]

        return '\n'.join(lines)

    def json_dump(self, contents: Any) -> str:
        return self.code_block(json.dumps(contents, indent=2, sort_keys=True, ensure_ascii=False), 'json')

    def code_block(self, contents: str, lang: str = '') -> str:
        return '```{}\n{}\n```'.format(lang, contents)

    def read_resource(self, path: str) -> Optional[str]:
        try:
            return sublime.load_resource(path)
        except Exception:
            return None


class LspCopyToClipboardFromBase64Command(sublime_plugin.ApplicationCommand):
    def run(self, contents: str = '') -> None:
        sublime.set_clipboard(b64decode(contents).decode())


class LspDumpWindowConfigs(sublime_plugin.WindowCommand):
    """
    Very basic command to dump all of the window's resolved configurations.
    """

    def run(self) -> None:
        view = self.window.new_file()
        view.set_scratch(True)
        view.set_name("Window {} configs".format(self.window.id()))
        view.settings().set("word_wrap", False)
        view.set_syntax_file("Packages/Python/Python.sublime-syntax")
        for config in windows.lookup(self.window).get_config_manager().get_configs():
            view.run_command("append", {"characters": str(config) + "\n"})


class LspDumpBufferCapabilities(sublime_plugin.TextCommand):
    """
    Very basic command to dump the current view's static and dynamically registered capabilities.
    """

    def run(self, edit: sublime.Edit) -> None:
        window = self.view.window()
        if not window:
            return
        file_name = self.view.file_name()
        if not file_name:
            return
        manager = windows.lookup(window)
        listener = manager.listener_for_view(self.view)
        if not listener or not any(listener.session_views_async()):
            sublime.error_message("There is no language server running for this view.")
            return
        v = window.new_file()
        v.set_scratch(True)
        v.assign_syntax("Packages/Markdown/Markdown.sublime-settings")
        v.set_name("{} (capabilities)".format(os.path.basename(file_name)))

        def p(s: str) -> None:
            v.run_command("append", {"characters": s + "\n"})

        def print_capabilities(capabilities: Capabilities) -> str:
            return "```json\n{}\n```".format(json.dumps(capabilities.get(), indent=4, sort_keys=True))

        for sv in listener.session_views_async():
            p("# {}\n".format(sv.session.config.name))
            p("## Global capabilities\n")
            p(print_capabilities(sv.session.capabilities) + "\n")
            p("## View-specific capabilities\n")
            p(print_capabilities(sv.session_buffer.capabilities) + "\n")


class ServerTestRunner(TransportCallbacks):
    """
    Used to start the server and collect any potential stderr output and the exit code.

    Server is automatically closed after defined timeout.
    """

    CLOSE_TIMEOUT_SEC = 2

    def __init__(
        self, config: ClientConfig, window: sublime.Window, on_close: Callable[[List[str], str, int], None]
    ) -> None:
        self._on_close = on_close
        self._transport = None  # type: Optional[Transport]
        self._resolved_command = []  # type: List[str]
        self._stderr_lines = []  # type: List[str]
        try:
            variables = extract_variables(window)
            plugin_class = get_plugin(config.name)
            if plugin_class is not None:
                if plugin_class.needs_update_or_installation():
                    plugin_class.install_or_update()
                additional_variables = plugin_class.additional_variables()
                if isinstance(additional_variables, dict):
                    variables.update(additional_variables)
            cwd = window.folders()[0] if window.folders() else None
            transport_config = config.resolve_transport_config(variables)
            self._resolved_command = transport_config.command
            self._transport = create_transport(transport_config, cwd, self)
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
        sublime.set_timeout(lambda: self._on_close(self._resolved_command, output, exit_code))

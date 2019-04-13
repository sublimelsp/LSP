import unittest
from unittesting import DeferrableTestCase
from unittest.mock import MagicMock
import sublime
import json
from LSP.plugin.completion import CompletionHandler, CompletionState, format_completion
from LSP.plugin.core.settings import client_configs, ClientConfig
from os.path import dirname, join

try:
    from typing import Dict, Optional
    assert Dict and Optional
except ImportError:
    pass


def load_completion_sample(name: str) -> 'Dict':
    return json.load(open(join(dirname(__file__), name + ".json")))


pyls_completion_sample = load_completion_sample("pyls_completion_sample")
clangd_completion_sample = load_completion_sample("clangd_completion_sample")
intelephense_completion_sample = load_completion_sample("intelephense_completion_sample")
powershell_completion_sample = load_completion_sample("powershell_completion_sample")


def create_completion_item(item: str, insert_text: 'Optional[str]' = None) -> dict:
    return {
        "label": item,
        "insertText": insert_text
    }


def create_completion_response(items):
    return {
        "items": list(map(create_completion_item, items))
    }


class FakeClient(object):

    def __init__(self):
        self.response = None
        pass

    def get_capability(self, capability_name: str):
        return {
            'triggerCharacters': ['.'],
            'resolveProvider': False
        }


SUPPORTED_SCOPE = "text.plain"
SUPPORTED_SYNTAX = "Lang.sublime-syntax"
test_client_config = ClientConfig('langls', [], None, [SUPPORTED_SCOPE], [SUPPORTED_SYNTAX], 'lang')
test_file_path = dirname(__file__) + "/testfile.txt"


@unittest.skip('asd')
class InitializationTests(DeferrableTestCase):

    def setUp(self):
        self.view = sublime.active_window().new_file()
        self.old_configs = client_configs.all
        client_configs.all = [test_client_config]

    def test_is_not_applicable(self):
        self.assertFalse(CompletionHandler.is_applicable(dict()))

    def test_is_applicable(self):
        self.assertEquals(len(client_configs.all), 1)
        self.assertTrue(CompletionHandler.is_applicable(dict(syntax=SUPPORTED_SYNTAX)))

    def test_not_enabled(self):
        handler = CompletionHandler(self.view)
        self.assertFalse(handler.initialized)
        self.assertFalse(handler.enabled)
        result = handler.on_query_completions("", [0])
        self.assertTrue(handler.initialized)
        self.assertFalse(handler.enabled)
        self.assertIsNone(result)

    def tearDown(self):
        client_configs.all = self.old_configs
        if self.view:
            self.view.set_scratch(True)
            self.view.window().focus_view(self.view)
            self.view.window().run_command("close_file")


@unittest.skip('asf')
class QueryCompletionsTests(unittest.TestCase):

    def setUp(self):
        self.view = sublime.active_window().open_file(test_file_path)
        self.old_configs = client_configs.all
        client_configs.all = [test_client_config]
        self.client = FakeClient()
        # add_window_client(sublime.active_window(), test_client_config.name, self.client)

    def test_enabled(self):
        self.view.run_command('insert', {"characters": '.'})

        self.client.send_request = MagicMock()

        handler = CompletionHandler(self.view)
        self.assertEquals(handler.state, CompletionState.IDLE)

        result = handler.on_query_completions("", [1])
        self.assertIsNotNone(result)
        items, mask = result
        self.assertEquals(len(items), 0)
        self.assertEquals(mask, sublime.INHIBIT_WORD_COMPLETIONS | sublime.INHIBIT_EXPLICIT_COMPLETIONS)

        self.assertTrue(handler.initialized)
        self.assertTrue(handler.enabled)
        self.assertEquals(handler.state, CompletionState.REQUESTING)

        self.client.send_request.assert_called_once()
        # time.sleep(1000)
        # self.assertEquals(len(handler.completions), 2)
        # self.assertEquals(handler.state, CompletionState.APPLYING)

        # running auto_complete command does not work
        # sublime does not know about the instance we registered here.
        # we do it directly here
        # items, mask = handler.on_query_completions("", [1])

        # self.assertEquals(len(items), 2)
        # self.assertEquals(mask, sublime.INHIBIT_WORD_COMPLETIONS | sublime.INHIBIT_EXPLICIT_COMPLETIONS)

    def tearDown(self):
        client_configs.all = self.old_configs
        if self.view:
            self.view.window().run_command("close_file")


class CompletionFormattingTests(DeferrableTestCase):

    def setUp(self):
        self.view = sublime.active_window().open_file(test_file_path)
        self.word_separators = self.view.settings().get("word_separators")
        self.assertTrue(self.word_separators)

    def test_only_label_item(self):
        result = format_completion(create_completion_item("asdf"), "a", self.word_separators)
        self.assertEqual(len(result), 2)
        self.assertEqual("asdf", result[0])
        self.assertEqual("asdf", result[1])

    def test_prefers_insert_text(self):
        result = format_completion(create_completion_item("asdf", "Asdf"), "A", self.word_separators)
        self.assertEqual(len(result), 2)
        self.assertEqual("asdf", result[0])
        self.assertEqual("Asdf", result[1])

    def test_ignores_text_edit(self):
        # partial completion from cursor (instead of full word) causes issues.
        item = {
            'insertText': '$true',
            'label': 'true',
            'textEdit': {
                'newText': 'rue',
                'range': {
                    'start': {'line': 0, 'character': 2},
                    'end': {'line': 0, 'character': 2}
                }
            }
        }
        result = format_completion(item, "t", self.word_separators)
        self.assertEqual(len(result), 2)
        self.assertEqual("true", result[0])
        self.assertEqual("rue", result[1])

    def test_ignore_label(self):
        # issue #368
        yield 100  # wait for file to be open
        item = {
            'insertTextFormat': 2,
            # insertText is present, but we should prefer textEdit instead.
            'insertText': 'const',
            'sortText': '3f800000const',
            'kind': 14,
            # Note the extra space here. We should ignore this!
            'label': ' const',
            'filterText': 'const',
            'textEdit': {
                'newText': 'const',
                'range': {
                    # Replace the single character that triggered the completion request.
                    'end': {'character': 13, 'line': 6},
                    'start': {'character': 12, 'line': 6}
                }
            }
        }
        handler = CompletionHandler(self.view)
        handler.last_location = 1
        handler.last_prefix = "c"
        result = format_completion(item, "c", self.word_separators)
        self.assertEqual(result, ('const\t  Keyword', 'const'))

    def test_text_edit_intelephense(self):
        yield 100  # wait for file to be open
        handler = CompletionHandler(self.view)
        handler.last_location = 1
        handler.last_prefix = "$"
        result = [format_completion(item, "$", self.word_separators) for item in intelephense_completion_sample]
        self.assertEqual(
            result,
            [
                ('$x\t  mixed', '\\$x'),
                ('$_ENV\t  array', '\\$_ENV'),
                ('$php_errormsg\t  string', '\\$php_errormsg'),
                ('$_FILES\t  array', '\\$_FILES'),
                ('$GLOBALS\t  array', '\\$GLOBALS'),
                ('$argc\t  int', '\\$argc'),
                ('$argv\t  array', '\\$argv'),
                ('$_GET\t  array', '\\$_GET'),
                ('$HTTP_RAW_POST_DATA\t  string', '\\$HTTP_RAW_POST_DATA'),
                ('$http_response_header\t  array', '\\$http_response_header'),
                ('$_POST\t  array', '\\$_POST'),
                ('$_REQUEST\t  array', '\\$_REQUEST'),
                ('$_SERVER\t  array', '\\$_SERVER'),
                ('$_SESSION\t  array', '\\$_SESSION'),
                ('$_COOKIE\t  array', '\\$_COOKIE'),
                ('$this\t  Variable', '\\$this')
            ]
        )

    def test_text_edit_clangd(self):
        yield 100  # wait for file to be open
        handler = CompletionHandler(self.view)
        handler.last_location = 1
        handler.last_prefix = "a"
        result = [format_completion(item, "a", self.word_separators) for item in clangd_completion_sample]
        # We should prefer textEdit over insertText. This test covers that.
        self.assertEqual(
            result,
            [
                ('argc\t  int', 'argc'),
                ('argv\t  const char **', 'argv'),
                ('alignas\t  Snippet', 'alignas(${1:expression})'),
                ('alignof\t  size_t', 'alignof(${1:type})'),
                ('auto\t  Keyword', 'auto'),
                ('static_assert\t  Snippet', 'static_assert(${1:expression}, ${2:message})'),
                ('a64l\t  long', 'a64l(${1:const char *__s})'),
                ('abort\t  void', 'abort()'),
                ('abs\t  int', 'abs(${1:int __x})'),
                ('aligned_alloc\t  void *', 'aligned_alloc(${1:size_t __alignment}, ${2:size_t __size})'),
                ('alloca\t  void *', 'alloca(${1:size_t __size})'),
                ('asctime\t  char *', 'asctime(${1:const struct tm *__tp})'),
                ('asctime_r\t  char *',
                 'asctime_r(${1:const struct tm *__restrict __tp}, ${2:char *__restrict __buf})'),
                ('asprintf\t  int', 'asprintf(${1:char **__restrict __ptr}, ${2:const char *__restrict __fmt, ...})'),
                ('at_quick_exit\t  int', 'at_quick_exit(${1:void (*__func)()})'),
                ('atexit\t  int', 'atexit(${1:void (*__func)()})'),
                ('atof\t  double', 'atof(${1:const char *__nptr})'),
                ('atoi\t  int', 'atoi(${1:const char *__nptr})'),
                ('atol\t  long', 'atol(${1:const char *__nptr})')
            ]
        )

    def test_missing_text_edit_but_we_do_have_insert_text_for_pyls(self):
        yield 100  # wait for file to be open
        handler = CompletionHandler(self.view)
        handler.last_location = 1
        handler.last_prefix = "a"
        result = [format_completion(item, "a", self.word_separators) for item in pyls_completion_sample]
        self.assertEqual(
            result,
            [
                ('abc\t  os', 'abc'),
                ('abort()\t  os', 'abort'),
                ('access(path, mode, dir_fd, effective_ids, follow_symlinks)\t  os',
                 'access(${1:path}, ${2:mode}, ${3:dir_fd}, ${4:effective_ids}, ${5:follow_symlinks})$0'),
                ('altsep\t  os', 'altsep'),
                ('chdir(path)\t  os', 'chdir(${1:path})$0'),
                ('chmod(path, mode, dir_fd, follow_symlinks)\t  os',
                 'chmod(${1:path}, ${2:mode}, ${3:dir_fd}, ${4:follow_symlinks})$0'),
                ('chown(path, uid, gid, dir_fd, follow_symlinks)\t  os',
                 'chown(${1:path}, ${2:uid}, ${3:gid}, ${4:dir_fd}, ${5:follow_symlinks})$0'),
                ('chroot(path)\t  os', 'chroot(${1:path})$0'),
                ('CLD_CONTINUED\t  os', 'CLD_CONTINUED'),
                ('CLD_DUMPED\t  os', 'CLD_DUMPED'),
                ('CLD_EXITED\t  os', 'CLD_EXITED'),
                ('CLD_TRAPPED\t  os', 'CLD_TRAPPED'),
                ('close(fd)\t  os', 'close(${1:fd})$0'),
                ('closerange(fd_low, fd_high)\t  os', 'closerange(${1:fd_low}, ${2:fd_high})$0'),
                ('confstr(name)\t  os', 'confstr(${1:name})$0'),
                ('confstr_names\t  os', 'confstr_names'),
                ('cpu_count()\t  os', 'cpu_count'),
                ('ctermid()\t  os', 'ctermid'),
                ('curdir\t  os', 'curdir'),
                ('defpath\t  os', 'defpath'),
                ('device_encoding(fd)\t  os', 'device_encoding(${1:fd})$0')
            ]
        )

    def test_text_edit_powershell(self):
        yield 100  # wait for file to be open
        # Note that the prefix is "e", not "$". This tests wether we can work around a sublime text quirk
        # where the prefix string does not start with a word separator and the completion contains two
        # word separators.
        # Notice in particular that the completion for e.g. $env:VISUAL is env:VISUAL.
        result = [format_completion(item, "e", self.word_separators) for item in powershell_completion_sample]
        self.assertEqual(
            result,
            [
                ('$Error\t  [ArrayList]', '\\$Error'),
                ('$ErrorActionPreference\t  [ActionPreference]', '\\$ErrorActionPreference'),
                ('$ErrorView\t  [string]', '\\$ErrorView'),
                ('$ExecutionContext\t  [EngineIntrinsics]', '\\$ExecutionContext'),
                ('$env:__CF_USER_TEXT_ENCODING\t  [string]', 'env:__CF_USER_TEXT_ENCODING'),
                ('$env:Apple_PubSub_Socket_Render\t  [string]', 'env:Apple_PubSub_Socket_Render'),
                ('$env:BROWSER\t  [string]', 'env:BROWSER'),
                ('$env:DISPLAY\t  [string]', 'env:DISPLAY'),
                ('$env:EDITOR\t  [string]', 'env:EDITOR'),
                ('$env:HOME\t  [string]', 'env:HOME'),
                ('$env:VISUAL\t  [string]', 'env:VISUAL'),
                ('$env:XPC_FLAGS\t  [string]', 'env:XPC_FLAGS'),
                ('$env:XPC_SERVICE_NAME\t  [string]', 'env:XPC_SERVICE_NAME'),
                ('$env:PATHEXT\t  Variable', 'env:PATHEXT'),
                ('$Env:\t  Variable', 'Env:')
            ]
        )

    def tearDown(self):
        if self.view:
            self.view.set_scratch(True)
            self.view.window().focus_view(self.view)
            self.view.window().run_command("close_file")

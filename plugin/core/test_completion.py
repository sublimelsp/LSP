import unittest
from os import path
import json
from .completion import format_completion, parse_completion_response
from .types import Settings
try:
    from typing import Optional, Dict
    assert Optional and Dict
except ImportError:
    pass


def load_completion_sample(name: str) -> 'Dict':
    return json.load(open(path.join(path.dirname(__file__), "../../tests/", name + ".json")))


pyls_completion_sample = load_completion_sample("pyls_completion_sample")
clangd_completion_sample = load_completion_sample("clangd_completion_sample")
intelephense_completion_sample = load_completion_sample("intelephense_completion_sample")


settings = Settings()


class CompletionResponseParsingTests(unittest.TestCase):

    def test_no_response(self):
        self.assertEqual(parse_completion_response(None), ([], False))

    def test_array_response(self):
        self.assertEqual(parse_completion_response([]), ([], False))

    def test_dict_response(self):
        self.assertEqual(parse_completion_response({'items': []}), ([], False))

    def test_incomplete_dict_response(self):
        self.assertEqual(parse_completion_response({'items': [], 'isIncomplete': True}), ([], True))


class CompletionFormattingTests(unittest.TestCase):

    def test_only_label_item(self):
        result = format_completion({"label": "asdf"}, 0, settings)
        self.assertEqual(len(result), 2)
        self.assertEqual("asdf", result[0])
        self.assertEqual("asdf", result[1])

    def test_prefer_label_over_filter_text(self):
        updated_settings = Settings()
        updated_settings.prefer_label_over_filter_text = True
        result = format_completion(
            {"label": "asdf", "insertText": "asdf", "filterText": "filterText"},
            0, updated_settings)
        self.assertEqual(len(result), 2)
        self.assertEqual("asdf", result[0])
        self.assertEqual("asdf", result[1])

    def test_prefers_insert_text(self):
        result = format_completion(
            {"label": "asdf", "insertText": "Asdf", "filterText": "asdf"},
            0, settings)
        self.assertEqual(len(result), 2)
        self.assertEqual("asdf", result[0])
        self.assertEqual("Asdf", result[1])

    def test_null_filter_text(self):
        result = format_completion(
            {"label": "asdf", "insertText": None, "filterText": None},
            0, settings)
        self.assertEqual(len(result), 2)
        self.assertEqual("asdf", result[0])
        self.assertEqual("asdf", result[1])

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

        result = format_completion(item, 0, settings)
        self.assertEqual(len(result), 2)
        self.assertEqual("$true", result[0])
        self.assertEqual("\\$true", result[1])

    def test_ignore_label(self):
        # issue #368
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
        last_col = 1
        result = format_completion(item, last_col, settings)
        self.assertEqual(result, ('const\t  Keyword', 'const'))

    def test_text_edit_intelephense(self):
        last_col = 1
        result = [format_completion(item, last_col, settings) for item in intelephense_completion_sample]
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
        # handler.last_location = 1
        # handler.last_prefix = ""
        last_col = 1
        result = [format_completion(item, last_col, settings) for item in clangd_completion_sample]
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
        last_col = 1
        result = [format_completion(item, last_col, settings) for item in pyls_completion_sample]
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

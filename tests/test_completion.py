import unittest
from unittesting import DeferrableTestCase
from unittest.mock import MagicMock
import sublime
import json
from LSP.plugin.completion import CompletionHandler, CompletionState
from LSP.plugin.core.settings import client_configs, ClientConfig
from os.path import dirname

# This was returned by the intelephense language server using the following
# buffer:
#
# <?php
#
# $x = $
intelephense_completion_sample = '''
[
  {
    "textEdit": {
      "range": {
        "end": {
          "character": 6,
          "line": 2
        },
        "start": {
          "character": 5,
          "line": 2
        }
      },
      "newText": "$x"
    },
    "label": "$x",
    "detail": "mixed",
    "data": {
      "fqsenHash": 1236,
      "uriId": 158
    },
    "kind": 6,
    "sortText": "$x"
  },
  {
    "textEdit": {
      "range": {
        "end": {
          "character": 6,
          "line": 2
        },
        "start": {
          "character": 5,
          "line": 2
        }
      },
      "newText": "$_ENV"
    },
    "label": "$_ENV",
    "detail": "array",
    "data": {
      "fqsenHash": 36145714,
      "uriId": 82
    },
    "kind": 6,
    "sortText": "z$_ENV"
  },
  {
    "textEdit": {
      "range": {
        "end": {
          "character": 6,
          "line": 2
        },
        "start": {
          "character": 5,
          "line": 2
        }
      },
      "newText": "$php_errormsg"
    },
    "label": "$php_errormsg",
    "detail": "string",
    "data": {
      "fqsenHash": -1647588988,
      "uriId": 82
    },
    "kind": 6,
    "sortText": "z$php_errormsg"
  },
  {
    "textEdit": {
      "range": {
        "end": {
          "character": 6,
          "line": 2
        },
        "start": {
          "character": 5,
          "line": 2
        }
      },
      "newText": "$_FILES"
    },
    "label": "$_FILES",
    "detail": "array",
    "data": {
      "fqsenHash": 377059964,
      "uriId": 82
    },
    "kind": 6,
    "sortText": "z$_FILES"
  },
  {
    "textEdit": {
      "range": {
        "end": {
          "character": 6,
          "line": 2
        },
        "start": {
          "character": 5,
          "line": 2
        }
      },
      "newText": "$GLOBALS"
    },
    "label": "$GLOBALS",
    "detail": "array",
    "data": {
      "fqsenHash": -844280724,
      "uriId": 82
    },
    "kind": 6,
    "sortText": "z$GLOBALS"
  },
  {
    "textEdit": {
      "range": {
        "end": {
          "character": 6,
          "line": 2
        },
        "start": {
          "character": 5,
          "line": 2
        }
      },
      "newText": "$argc"
    },
    "label": "$argc",
    "detail": "int",
    "data": {
      "fqsenHash": 36249329,
      "uriId": 82
    },
    "kind": 6,
    "sortText": "z$argc"
  },
  {
    "textEdit": {
      "range": {
        "end": {
          "character": 6,
          "line": 2
        },
        "start": {
          "character": 5,
          "line": 2
        }
      },
      "newText": "$argv"
    },
    "label": "$argv",
    "detail": "array",
    "data": {
      "fqsenHash": 36249348,
      "uriId": 82
    },
    "kind": 6,
    "sortText": "z$argv"
  },
  {
    "textEdit": {
      "range": {
        "end": {
          "character": 6,
          "line": 2
        },
        "start": {
          "character": 5,
          "line": 2
        }
      },
      "newText": "$_GET"
    },
    "label": "$_GET",
    "detail": "array",
    "data": {
      "fqsenHash": 36147355,
      "uriId": 82
    },
    "kind": 6,
    "sortText": "z$_GET"
  },
  {
    "textEdit": {
      "range": {
        "end": {
          "character": 6,
          "line": 2
        },
        "start": {
          "character": 5,
          "line": 2
        }
      },
      "newText": "$HTTP_RAW_POST_DATA"
    },
    "label": "$HTTP_RAW_POST_DATA",
    "detail": "string",
    "data": {
      "fqsenHash": 1354318879,
      "uriId": 82
    },
    "kind": 6,
    "sortText": "z$HTTP_RAW_POST_DATA"
  },
  {
    "textEdit": {
      "range": {
        "end": {
          "character": 6,
          "line": 2
        },
        "start": {
          "character": 5,
          "line": 2
        }
      },
      "newText": "$http_response_header"
    },
    "label": "$http_response_header",
    "detail": "array",
    "data": {
      "fqsenHash": 985564344,
      "uriId": 82
    },
    "kind": 6,
    "sortText": "z$http_response_header"
  },
  {
    "textEdit": {
      "range": {
        "end": {
          "character": 6,
          "line": 2
        },
        "start": {
          "character": 5,
          "line": 2
        }
      },
      "newText": "$_POST"
    },
    "label": "$_POST",
    "detail": "array",
    "data": {
      "fqsenHash": 1120845787,
      "uriId": 82
    },
    "kind": 6,
    "sortText": "z$_POST"
  },
  {
    "textEdit": {
      "range": {
        "end": {
          "character": 6,
          "line": 2
        },
        "start": {
          "character": 5,
          "line": 2
        }
      },
      "newText": "$_REQUEST"
    },
    "label": "$_REQUEST",
    "detail": "array",
    "data": {
      "fqsenHash": -766918316,
      "uriId": 82
    },
    "kind": 6,
    "sortText": "z$_REQUEST"
  },
  {
    "textEdit": {
      "range": {
        "end": {
          "character": 6,
          "line": 2
        },
        "start": {
          "character": 5,
          "line": 2
        }
      },
      "newText": "$_SERVER"
    },
    "label": "$_SERVER",
    "detail": "array",
    "data": {
      "fqsenHash": -827363394,
      "uriId": 82
    },
    "kind": 6,
    "sortText": "z$_SERVER"
  },
  {
    "textEdit": {
      "range": {
        "end": {
          "character": 6,
          "line": 2
        },
        "start": {
          "character": 5,
          "line": 2
        }
      },
      "newText": "$_SESSION"
    },
    "label": "$_SESSION",
    "detail": "array",
    "data": {
      "fqsenHash": 122376539,
      "uriId": 82
    },
    "kind": 6,
    "sortText": "z$_SESSION"
  },
  {
    "textEdit": {
      "range": {
        "end": {
          "character": 6,
          "line": 2
        },
        "start": {
          "character": 5,
          "line": 2
        }
      },
      "newText": "$_COOKIE"
    },
    "label": "$_COOKIE",
    "detail": "array",
    "data": {
      "fqsenHash": -1276294433,
      "uriId": 82
    },
    "kind": 6,
    "sortText": "z$_COOKIE"
  },
  {
    "label": "$this",
    "sortText": "$this",
    "kind": 6,
    "textEdit": {
      "range": {
        "end": {
          "character": 6,
          "line": 2
        },
        "start": {
          "character": 5,
          "line": 2
        }
      },
      "newText": "$this"
    }
  }
]
'''


# this was returned by the clangd language server using the following file:
#
# int main(int argc, char const *argv[])
# {
#     a
#     return 0;
# }
#
# I removed some completion items because this should be enough.
clangd_completion_sample = '''
[
  {
    "insertTextFormat": 2,
    "textEdit": {
      "range": {
        "end": {
          "character": 5,
          "line": 2
        },
        "start": {
          "character": 4,
          "line": 2
        }
      },
      "newText": "argc"
    },
    "filterText": "argc",
    "insertText": "argc",
    "label": "argc",
    "detail": "int",
    "kind": 6,
    "sortText": "3e2cccccargc"
  },
  {
    "insertTextFormat": 2,
    "textEdit": {
      "range": {
        "end": {
          "character": 5,
          "line": 2
        },
        "start": {
          "character": 4,
          "line": 2
        }
      },
      "newText": "argv"
    },
    "filterText": "argv",
    "insertText": "argv",
    "label": "argv",
    "detail": "const char **",
    "kind": 6,
    "sortText": "3e2cccccargv"
  },
  {
    "insertTextFormat": 2,
    "textEdit": {
      "range": {
        "end": {
          "character": 5,
          "line": 2
        },
        "start": {
          "character": 4,
          "line": 2
        }
      },
      "newText": "alignas(${1:expression})"
    },
    "filterText": "alignas",
    "insertText": "alignas(${1:expression})",
    "label": "alignas(expression)",
    "kind": 15,
    "sortText": "3f800000alignas"
  },
  {
    "insertTextFormat": 2,
    "textEdit": {
      "range": {
        "end": {
          "character": 5,
          "line": 2
        },
        "start": {
          "character": 4,
          "line": 2
        }
      },
      "newText": "alignof(${1:type})"
    },
    "filterText": "alignof",
    "insertText": "alignof(${1:type})",
    "label": "alignof(type)",
    "detail": "size_t",
    "kind": 15,
    "sortText": "3f800000alignof"
  },
  {
    "insertTextFormat": 2,
    "textEdit": {
      "range": {
        "end": {
          "character": 5,
          "line": 2
        },
        "start": {
          "character": 4,
          "line": 2
        }
      },
      "newText": "auto"
    },
    "filterText": "auto",
    "insertText": "auto",
    "label": "auto",
    "kind": 14,
    "sortText": "3f800000auto"
  },
  {
    "insertTextFormat": 2,
    "textEdit": {
      "range": {
        "end": {
          "character": 5,
          "line": 2
        },
        "start": {
          "character": 4,
          "line": 2
        }
      },
      "newText": "static_assert(${1:expression}, ${2:message})"
    },
    "filterText": "static_assert",
    "insertText": "static_assert(${1:expression}, ${2:message})",
    "label": "static_assert(expression, message)",
    "kind": 15,
    "sortText": "40555555static_assert"
  },
  {
    "insertTextFormat": 2,
    "textEdit": {
      "range": {
        "end": {
          "character": 5,
          "line": 2
        },
        "start": {
          "character": 4,
          "line": 2
        }
      },
      "newText": "a64l(${1:const char *__s})"
    },
    "filterText": "a64l",
    "insertText": "a64l(${1:const char *__s})",
    "label": "a64l(const char *__s)",
    "detail": "long",
    "kind": 3,
    "sortText": "40a7b70ba64l"
  },
  {
    "insertTextFormat": 2,
    "textEdit": {
      "range": {
        "end": {
          "character": 5,
          "line": 2
        },
        "start": {
          "character": 4,
          "line": 2
        }
      },
      "newText": "abort()"
    },
    "filterText": "abort",
    "insertText": "abort()",
    "label": "abort()",
    "detail": "void",
    "kind": 3,
    "sortText": "40a7b70babort"
  },
  {
    "insertTextFormat": 2,
    "textEdit": {
      "range": {
        "end": {
          "character": 5,
          "line": 2
        },
        "start": {
          "character": 4,
          "line": 2
        }
      },
      "newText": "abs(${1:int __x})"
    },
    "filterText": "abs",
    "insertText": "abs(${1:int __x})",
    "label": "abs(int __x)",
    "detail": "int",
    "kind": 3,
    "sortText": "40a7b70babs"
  },
  {
    "insertTextFormat": 2,
    "textEdit": {
      "range": {
        "end": {
          "character": 5,
          "line": 2
        },
        "start": {
          "character": 4,
          "line": 2
        }
      },
      "newText": "aligned_alloc(${1:size_t __alignment}, ${2:size_t __size})"
    },
    "filterText": "aligned_alloc",
    "insertText": "aligned_alloc(${1:size_t __alignment}, ${2:size_t __size})",
    "label": "aligned_alloc(size_t __alignment, size_t __size)",
    "detail": "void *",
    "kind": 3,
    "sortText": "40a7b70baligned_alloc"
  },
  {
    "insertTextFormat": 2,
    "textEdit": {
      "range": {
        "end": {
          "character": 5,
          "line": 2
        },
        "start": {
          "character": 4,
          "line": 2
        }
      },
      "newText": "alloca(${1:size_t __size})"
    },
    "filterText": "alloca",
    "insertText": "alloca(${1:size_t __size})",
    "label": "alloca(size_t __size)",
    "detail": "void *",
    "kind": 3,
    "sortText": "40a7b70balloca"
  },
  {
    "insertTextFormat": 2,
    "textEdit": {
      "range": {
        "end": {
          "character": 5,
          "line": 2
        },
        "start": {
          "character": 4,
          "line": 2
        }
      },
      "newText": "asctime(${1:const struct tm *__tp})"
    },
    "filterText": "asctime",
    "insertText": "asctime(${1:const struct tm *__tp})",
    "label": "asctime(const struct tm *__tp)",
    "detail": "char *",
    "kind": 3,
    "sortText": "40a7b70basctime"
  },
  {
    "insertTextFormat": 2,
    "textEdit": {
      "range": {
        "end": {
          "character": 5,
          "line": 2
        },
        "start": {
          "character": 4,
          "line": 2
        }
      },
      "newText": "asctime_r(${1:const struct tm *__restrict __tp}, ${2:char *__restrict __buf})"
    },
    "filterText": "asctime_r",
    "insertText": "asctime_r(${1:const struct tm *__restrict __tp}, ${2:char *__restrict __buf})",
    "label": "asctime_r(const struct tm *__restrict __tp, char *__restrict __buf)",
    "detail": "char *",
    "kind": 3,
    "sortText": "40a7b70basctime_r"
  },
  {
    "insertTextFormat": 2,
    "textEdit": {
      "range": {
        "end": {
          "character": 5,
          "line": 2
        },
        "start": {
          "character": 4,
          "line": 2
        }
      },
      "newText": "asprintf(${1:char **__restrict __ptr}, ${2:const char *__restrict __fmt, ...})"
    },
    "filterText": "asprintf",
    "insertText": "asprintf(${1:char **__restrict __ptr}, ${2:const char *__restrict __fmt, ...})",
    "label": "asprintf(char **__restrict __ptr, const char *__restrict __fmt, ...)",
    "detail": "int",
    "kind": 3,
    "sortText": "40a7b70basprintf"
  },
  {
    "insertTextFormat": 2,
    "textEdit": {
      "range": {
        "end": {
          "character": 5,
          "line": 2
        },
        "start": {
          "character": 4,
          "line": 2
        }
      },
      "newText": "at_quick_exit(${1:void (*__func)()})"
    },
    "filterText": "at_quick_exit",
    "insertText": "at_quick_exit(${1:void (*__func)()})",
    "label": "at_quick_exit(void (*__func)())",
    "detail": "int",
    "kind": 3,
    "sortText": "40a7b70bat_quick_exit"
  },
  {
    "insertTextFormat": 2,
    "textEdit": {
      "range": {
        "end": {
          "character": 5,
          "line": 2
        },
        "start": {
          "character": 4,
          "line": 2
        }
      },
      "newText": "atexit(${1:void (*__func)()})"
    },
    "filterText": "atexit",
    "insertText": "atexit(${1:void (*__func)()})",
    "label": "atexit(void (*__func)())",
    "detail": "int",
    "kind": 3,
    "sortText": "40a7b70batexit"
  },
  {
    "insertTextFormat": 2,
    "textEdit": {
      "range": {
        "end": {
          "character": 5,
          "line": 2
        },
        "start": {
          "character": 4,
          "line": 2
        }
      },
      "newText": "atof(${1:const char *__nptr})"
    },
    "filterText": "atof",
    "insertText": "atof(${1:const char *__nptr})",
    "label": "atof(const char *__nptr)",
    "detail": "double",
    "kind": 3,
    "sortText": "40a7b70batof"
  },
  {
    "insertTextFormat": 2,
    "textEdit": {
      "range": {
        "end": {
          "character": 5,
          "line": 2
        },
        "start": {
          "character": 4,
          "line": 2
        }
      },
      "newText": "atoi(${1:const char *__nptr})"
    },
    "filterText": "atoi",
    "insertText": "atoi(${1:const char *__nptr})",
    "label": "atoi(const char *__nptr)",
    "detail": "int",
    "kind": 3,
    "sortText": "40a7b70batoi"
  },
  {
    "insertTextFormat": 2,
    "textEdit": {
      "range": {
        "end": {
          "character": 5,
          "line": 2
        },
        "start": {
          "character": 4,
          "line": 2
        }
      },
      "newText": "atol(${1:const char *__nptr})"
    },
    "filterText": "atol",
    "insertText": "atol(${1:const char *__nptr})",
    "label": "atol(const char *__nptr)",
    "detail": "long",
    "kind": 3,
    "sortText": "40a7b70batol"
  }
]
'''


def create_completion_item(item: str, insert_text: 'Optional[str]'=None) -> dict:
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

    def test_only_label_item(self):
        handler = CompletionHandler(self.view)
        result = handler.format_completion(create_completion_item("asdf"))
        self.assertEqual(len(result), 2)
        self.assertEqual("asdf", result[0])
        self.assertEqual("asdf", result[1])

    def test_prefers_insert_text(self):
        handler = CompletionHandler(self.view)
        result = handler.format_completion(create_completion_item("asdf", "Asdf"))
        self.assertEqual(len(result), 2)
        self.assertEqual("Asdf", result[0])
        self.assertEqual("Asdf", result[1])

    def test_ignores_text_edit(self):
        handler = CompletionHandler(self.view)

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

        result = handler.format_completion(item)
        self.assertEqual(len(result), 2)
        self.assertEqual("$true", result[0])
        self.assertEqual("\\$true", result[1])

    def test_item_with_partial_edit(self):
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
        handler.last_prefix = ""
        result = handler.format_completion(item)
        self.assertEqual(result, ('const\t  Keyword', 'const'))

    def test_text_edit1(self):
        yield 100  # wait for file to be open
        items = json.loads(intelephense_completion_sample)
        handler = CompletionHandler(self.view)
        handler.last_location = 1
        handler.last_prefix = ""
        result = [handler.format_completion(item) for item in items]
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

    def test_text_edit2(self):
        yield 100  # wait for file to be open
        items = json.loads(clangd_completion_sample)
        handler = CompletionHandler(self.view)
        handler.last_location = 1
        handler.last_prefix = ""
        result = [handler.format_completion(item) for item in items]
        # We should prefer textEdit over insertText. This test covers that.
        self.assertEqual(
            result,
            [
                ('argc\t  int', 'argc'),  # noqa: E501
                ('argv\t  const char **', 'argv'),  # noqa: E501
                ('alignas(${1:expression})\t  Snippet', 'alignas(${1:expression})'),  # noqa: E501
                ('alignof(${1:type})\t  size_t', 'alignof(${1:type})'),  # noqa: E501
                ('auto\t  Keyword', 'auto'),  # noqa: E501
                ('static_assert(${1:expression}, ${2:message})\t  Snippet', 'static_assert(${1:expression}, ${2:message})'),  # noqa: E501
                ('a64l(${1:const char *__s})\t  long', 'a64l(${1:const char *__s})'),  # noqa: E501
                ('abort()\t  void', 'abort()'),  # noqa: E501
                ('abs(${1:int __x})\t  int', 'abs(${1:int __x})'),  # noqa: E501
                ('aligned_alloc(${1:size_t __alignment}, ${2:size_t __size})\t  void *', 'aligned_alloc(${1:size_t __alignment}, ${2:size_t __size})'),  # noqa: E501
                ('alloca(${1:size_t __size})\t  void *', 'alloca(${1:size_t __size})'),  # noqa: E501
                ('asctime(${1:const struct tm *__tp})\t  char *', 'asctime(${1:const struct tm *__tp})'),  # noqa: E501
                ('asctime_r(${1:const struct tm *__restrict __tp}, ${2:char *__restrict __buf})\t  char *', 'asctime_r(${1:const struct tm *__restrict __tp}, ${2:char *__restrict __buf})'),  # noqa: E501
                ('asprintf(${1:char **__restrict __ptr}, ${2:const char *__restrict __fmt, ...})\t  int', 'asprintf(${1:char **__restrict __ptr}, ${2:const char *__restrict __fmt, ...})'),  # noqa: E501
                ('at_quick_exit(${1:void (*__func)()})\t  int', 'at_quick_exit(${1:void (*__func)()})'),  # noqa: E501
                ('atexit(${1:void (*__func)()})\t  int', 'atexit(${1:void (*__func)()})'),  # noqa: E501
                ('atof(${1:const char *__nptr})\t  double', 'atof(${1:const char *__nptr})'),  # noqa: E501
                ('atoi(${1:const char *__nptr})\t  int', 'atoi(${1:const char *__nptr})'),  # noqa: E501
                ('atol(${1:const char *__nptr})\t  long', 'atol(${1:const char *__nptr})')  # noqa: E501
            ]
        )

    def tearDown(self):
        if self.view:
            self.view.set_scratch(True)
            self.view.window().focus_view(self.view)
            self.view.window().run_command("close_file")

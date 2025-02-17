from __future__ import annotations
from copy import deepcopy
from LSP.plugin.code_actions import get_matching_on_save_kinds, kinds_include_kind
from LSP.plugin.core.constants import RegionKey
from LSP.plugin.core.protocol import Point, Range
from LSP.plugin.core.url import filename_to_uri
from LSP.plugin.core.views import entire_content
from LSP.plugin.documents import DocumentSyncListener
from LSP.plugin.core.views import versioned_text_document_identifier
from setup import TextDocumentTestCase
from test_single_document import TEST_FILE_PATH
from typing import Any, Generator
import unittest
import sublime

TEST_FILE_URI = filename_to_uri(TEST_FILE_PATH)


def edit_to_lsp(edit: tuple[str, Range]) -> dict[str, Any]:
    return {"newText": edit[0], "range": edit[1]}


def range_from_points(start: Point, end: Point) -> Range:
    return {
        'start': start.to_lsp(),
        'end': end.to_lsp()
    }


def create_code_action_edit(view: sublime.View, version: int, edits: list[tuple[str, Range]]) -> dict[str, Any]:
    return {
        "documentChanges": [
            {
                "textDocument": versioned_text_document_identifier(view, version),
                "edits": list(map(edit_to_lsp, edits))
            }
        ]
    }


def create_command(command_name: str, command_args: list[Any] | None = None) -> dict[str, Any]:
    result: dict[str, Any] = {"command": command_name}
    if command_args is not None:
        result["arguments"] = command_args
    return result


def create_test_code_action(view: sublime.View, version: int, edits: list[tuple[str, Range]],
                            kind: str | None = None) -> dict[str, Any]:
    action = {
        "title": "Fix errors",
        "edit": create_code_action_edit(view, version, edits)
    }
    if kind:
        action['kind'] = kind
    return action


def create_test_code_action2(command_name: str, command_args: list[Any] | None = None,
                             kind: str | None = None) -> dict[str, Any]:
    action = {
        "title": "Fix errors",
        "command": create_command(command_name, command_args)
    }
    if kind:
        action['kind'] = kind
    return action


def create_disabled_code_action(view: sublime.View, version: int, edits: list[tuple[str, Range]]) -> dict[str, Any]:
    action = {
        "title": "Fix errors",
        "edit": create_code_action_edit(view, version, edits),
        "disabled": {
            "reason": "Do not use"
        },
    }
    return action


def create_test_diagnostics(diagnostics: list[tuple[str, Range]]) -> dict:
    def diagnostic_to_lsp(diagnostic: tuple[str, Range]) -> dict:
        message, range = diagnostic
        return {
            "message": message,
            "range": range
        }
    return {
        "uri": TEST_FILE_URI,
        "diagnostics": list(map(diagnostic_to_lsp, diagnostics))
    }


class CodeActionsOnSaveTestCase(TextDocumentTestCase):

    @classmethod
    def init_view_settings(cls) -> None:
        super().init_view_settings()
        # "quickfix" is not supported but its here for testing purposes
        cls.view.settings().set('lsp_code_actions_on_save', {'source.fixAll': True, 'quickfix': True})

    @classmethod
    def get_test_server_capabilities(cls) -> dict:
        capabilities = deepcopy(super().get_test_server_capabilities())
        capabilities['capabilities']['codeActionProvider'] = {'codeActionKinds': ['quickfix', 'source.fixAll']}
        return capabilities

    def doCleanups(self) -> Generator:
        yield from self.await_clear_view_and_save()
        yield from super().doCleanups()

    def test_applies_matching_kind(self) -> Generator:
        yield from self._setup_document_with_missing_semicolon()
        code_action_kind = 'source.fixAll'
        code_action = create_test_code_action(
            self.view,
            self.view.change_count(),
            [(';', range_from_points(Point(0, 11), Point(0, 11)))],
            code_action_kind
        )
        self.set_response('textDocument/codeAction', [code_action])
        self.view.run_command('lsp_save', {'async': True})
        yield from self.await_message('textDocument/codeAction')
        yield from self.await_message('textDocument/didSave')
        self.assertEqual(entire_content(self.view), 'const x = 1;')
        self.assertEqual(self.view.is_dirty(), False)

    def test_requests_with_diagnostics(self) -> Generator:
        yield from self._setup_document_with_missing_semicolon()
        code_action_kind = 'source.fixAll'
        code_action = create_test_code_action(
            self.view,
            self.view.change_count(),
            [(';', range_from_points(Point(0, 11), Point(0, 11)))],
            code_action_kind
        )
        self.set_response('textDocument/codeAction', [code_action])
        self.view.run_command('lsp_save', {'async': True})
        code_action_request = yield from self.await_message('textDocument/codeAction')
        self.assertEqual(len(code_action_request['context']['diagnostics']), 1)
        self.assertEqual(code_action_request['context']['diagnostics'][0]['message'], 'Missing semicolon')
        yield from self.await_message('textDocument/didSave')
        self.assertEqual(entire_content(self.view), 'const x = 1;')
        self.assertEqual(self.view.is_dirty(), False)

    def test_applies_only_one_pass(self) -> Generator:
        self.insert_characters('const x = 1')
        initial_change_count = self.view.change_count()
        yield from self.await_client_notification(
            "textDocument/publishDiagnostics",
            create_test_diagnostics([
                ('Missing semicolon', range_from_points(Point(0, 11), Point(0, 11))),
            ])
        )
        code_action_kind = 'source.fixAll'
        yield from self.set_responses([
            (
                'textDocument/codeAction',
                [
                    create_test_code_action(
                        self.view,
                        initial_change_count,
                        [(';', range_from_points(Point(0, 11), Point(0, 11)))],
                        code_action_kind
                    )
                ]
            ),
            (
                'textDocument/codeAction',
                [
                    create_test_code_action(
                        self.view,
                        initial_change_count + 1,
                        [('\nAnd again!', range_from_points(Point(0, 12), Point(0, 12)))],
                        code_action_kind
                    )
                ]
            ),
        ])
        self.view.run_command('lsp_save', {'async': True})
        # Wait for the view to be saved
        yield lambda: not self.view.is_dirty()
        self.assertEqual(entire_content(self.view), 'const x = 1;')

    def test_applies_immediately_after_text_change(self) -> Generator:
        self.insert_characters('const x = 1')
        code_action_kind = 'source.fixAll'
        code_action = create_test_code_action(
            self.view,
            self.view.change_count(),
            [(';', range_from_points(Point(0, 11), Point(0, 11)))],
            code_action_kind
        )
        self.set_response('textDocument/codeAction', [code_action])
        self.view.run_command('lsp_save', {'async': True})
        yield from self.await_message('textDocument/codeAction')
        yield from self.await_message('textDocument/didSave')
        self.assertEqual(entire_content(self.view), 'const x = 1;')
        self.assertEqual(self.view.is_dirty(), False)

    def test_no_fix_on_non_matching_kind(self) -> Generator:
        yield from self._setup_document_with_missing_semicolon()
        initial_content = 'const x = 1'
        self.view.run_command('lsp_save', {'async': True})
        yield from self.await_message('textDocument/didSave')
        self.assertEqual(entire_content(self.view), initial_content)
        self.assertEqual(self.view.is_dirty(), False)

    def test_does_not_apply_unsupported_kind(self) -> Generator:
        yield from self._setup_document_with_missing_semicolon()
        code_action_kind = 'quickfix'
        code_action = create_test_code_action(
            self.view,
            self.view.change_count(),
            [(';', range_from_points(Point(0, 11), Point(0, 11)))],
            code_action_kind
        )
        self.set_response('textDocument/codeAction', [code_action])
        self.view.run_command('lsp_save', {'async': True})
        yield from self.await_message('textDocument/didSave')
        self.assertEqual(entire_content(self.view), 'const x = 1')

    def _setup_document_with_missing_semicolon(self) -> Generator:
        self.insert_characters('const x = 1')
        yield from self.await_message("textDocument/didChange")
        yield from self.await_client_notification(
            "textDocument/publishDiagnostics",
            create_test_diagnostics([
                ('Missing semicolon', range_from_points(Point(0, 11), Point(0, 11))),
            ])
        )


class CodeActionMatchingTestCase(unittest.TestCase):
    def test_does_not_match(self) -> None:
        actual = get_matching_on_save_kinds({'a.x': True}, ['a.b'])
        expected: list[str] = []
        self.assertEqual(actual, expected)

    def test_matches_exact_action(self) -> None:
        actual = get_matching_on_save_kinds({'a.b': True}, ['a.b'])
        expected = ['a.b']
        self.assertEqual(actual, expected)

    def test_matches_more_specific_action(self) -> None:
        actual = get_matching_on_save_kinds({'a.b': True}, ['a.b.c'])
        expected = ['a.b.c']
        self.assertEqual(actual, expected)

    def test_does_not_match_disabled_action(self) -> None:
        actual = get_matching_on_save_kinds({'a.b': True, 'a.b.c': False}, ['a.b.c'])
        expected: list[str] = []
        self.assertEqual(actual, expected)

    def test_kind_matching(self) -> None:
        # Positive
        self.assertTrue(kinds_include_kind(['a'], 'a.b'))
        self.assertTrue(kinds_include_kind(['a.b'], 'a.b'))
        self.assertTrue(kinds_include_kind(['a.b', 'b'], 'b.c'))
        # Negative
        self.assertFalse(kinds_include_kind(['a'], 'b.a'))
        self.assertFalse(kinds_include_kind(['a.b'], 'b'))
        self.assertFalse(kinds_include_kind(['a.b'], 'a'))
        self.assertFalse(kinds_include_kind(['aa'], 'a'))
        self.assertFalse(kinds_include_kind(['aa.b'], 'a'))
        self.assertFalse(kinds_include_kind(['aa.b'], 'b'))


class CodeActionsListenerTestCase(TextDocumentTestCase):
    def setUp(self) -> Generator:
        yield from super().setUp()
        self.original_debounce_time = DocumentSyncListener.debounce_time
        DocumentSyncListener.debounce_time = 0

    def tearDown(self) -> None:
        DocumentSyncListener.debounce_time = self.original_debounce_time
        super().tearDown()

    @classmethod
    def get_test_server_capabilities(cls) -> dict:
        capabilities = deepcopy(super().get_test_server_capabilities())
        capabilities['capabilities']['codeActionProvider'] = {}
        return capabilities

    def test_requests_with_diagnostics(self) -> Generator:
        initial_content = 'a\nb\nc'
        self.insert_characters(initial_content)
        yield from self.await_message('textDocument/didChange')
        range_a = range_from_points(Point(0, 0), Point(0, 1))
        range_b = range_from_points(Point(1, 0), Point(1, 1))
        range_c = range_from_points(Point(2, 0), Point(2, 1))
        yield from self.await_client_notification(
            "textDocument/publishDiagnostics",
            create_test_diagnostics([('issue a', range_a), ('issue b', range_b), ('issue c', range_c)])
        )
        code_action_a = create_test_code_action(self.view, self.view.change_count(), [("A", range_a)])
        code_action_b = create_test_code_action(self.view, self.view.change_count(), [("B", range_b)])
        self.set_response('textDocument/codeAction', [code_action_a, code_action_b])
        self.view.run_command('lsp_selection_set', {"regions": [(0, 3)]})  # Select a and b.
        yield 100
        params = yield from self.await_message('textDocument/codeAction')
        self.assertEqual(params['range']['start']['line'], 0)
        self.assertEqual(params['range']['start']['character'], 0)
        self.assertEqual(params['range']['end']['line'], 1)
        self.assertEqual(params['range']['end']['character'], 1)
        self.assertEqual(len(params['context']['diagnostics']), 2)
        annotations_range = self.view.get_regions(RegionKey.CODE_ACTION)
        self.assertEqual(len(annotations_range), 1)
        self.assertEqual(annotations_range[0].a, 3)
        self.assertEqual(annotations_range[0].b, 0)

    def test_requests_with_no_diagnostics(self) -> Generator:
        initial_content = 'a\nb\nc'
        self.insert_characters(initial_content)
        yield from self.await_message("textDocument/didChange")
        range_a = range_from_points(Point(0, 0), Point(0, 1))
        range_b = range_from_points(Point(1, 0), Point(1, 1))
        code_action1 = create_test_code_action(self.view, 0, [("A", range_a)])
        code_action2 = create_test_code_action(self.view, 0, [("B", range_b)])
        self.set_response('textDocument/codeAction', [code_action1, code_action2])
        self.view.run_command('lsp_selection_set', {"regions": [(0, 3)]})  # Select a and b.
        yield 100
        params = yield from self.await_message('textDocument/codeAction')
        self.assertEqual(params['range']['start']['line'], 0)
        self.assertEqual(params['range']['start']['character'], 0)
        self.assertEqual(params['range']['end']['line'], 1)
        self.assertEqual(params['range']['end']['character'], 1)
        self.assertEqual(len(params['context']['diagnostics']), 0)
        annotations_range = self.view.get_regions(RegionKey.CODE_ACTION)
        self.assertEqual(len(annotations_range), 1)
        self.assertEqual(annotations_range[0].a, 3)
        self.assertEqual(annotations_range[0].b, 0)

    def test_excludes_disabled_code_actions(self) -> Generator:
        initial_content = 'a\n'
        self.insert_characters(initial_content)
        yield from self.await_message("textDocument/didChange")
        code_action = create_disabled_code_action(
            self.view,
            self.view.change_count(),
            [(';', range_from_points(Point(0, 0), Point(0, 1)))]
        )
        self.set_response('textDocument/codeAction', [code_action])
        self.view.run_command('lsp_selection_set', {"regions": [(0, 1)]})  # Select a
        yield 100
        yield from self.await_message('textDocument/codeAction')
        code_action_ranges = self.view.get_regions(RegionKey.CODE_ACTION)
        self.assertEqual(len(code_action_ranges), 0)

    def test_extends_range_to_include_diagnostics(self) -> Generator:
        self.insert_characters('x diagnostic')
        yield from self.await_message("textDocument/didChange")
        yield from self.await_client_notification(
            "textDocument/publishDiagnostics",
            create_test_diagnostics([
                ('diagnostic word', range_from_points(Point(0, 2), Point(0, 12))),
                ('all content', range_from_points(Point(0, 0), Point(0, 12))),
            ])
        )
        self.view.run_command('lsp_selection_set', {"regions": [(0, 5)]})
        yield 100
        params = yield from self.await_message('textDocument/codeAction')
        # Range should be extended to include range of all intersecting diagnostics
        self.assertEqual(params['range']['start']['line'], 0)
        self.assertEqual(params['range']['start']['character'], 0)
        self.assertEqual(params['range']['end']['line'], 0)
        self.assertEqual(params['range']['end']['character'], 12)
        self.assertEqual(len(params['context']['diagnostics']), 2)


class CodeActionsTestCase(TextDocumentTestCase):

    @classmethod
    def get_test_server_capabilities(cls) -> dict:
        capabilities = deepcopy(super().get_test_server_capabilities())
        capabilities['capabilities']['codeActionProvider'] = {"resolveProvider": True}
        return capabilities

    def test_requests_code_actions_on_newly_published_diagnostics(self) -> Generator:
        self.insert_characters('a\nb')
        yield from self.await_message("textDocument/didChange")
        yield from self.await_client_notification(
            "textDocument/publishDiagnostics",
            create_test_diagnostics([
                ('issue a', range_from_points(Point(0, 0), Point(0, 1))),
                ('issue b', range_from_points(Point(1, 0), Point(1, 1)))
            ])
        )
        params = yield from self.await_message('textDocument/codeAction')
        self.assertEqual(params['range']['start']['line'], 1)
        self.assertEqual(params['range']['start']['character'], 0)
        self.assertEqual(params['range']['end']['line'], 1)
        self.assertEqual(params['range']['end']['character'], 1)
        self.assertEqual(len(params['context']['diagnostics']), 1)

    def test_applies_code_action_with_matching_document_version(self) -> Generator:
        code_action = create_test_code_action(self.view, 3, [
            ("c", range_from_points(Point(0, 0), Point(0, 1))),
            ("d", range_from_points(Point(1, 0), Point(1, 1))),
        ])
        self.insert_characters('a\nb')
        yield from self.await_message("textDocument/didChange")
        self.assertEqual(self.view.change_count(), 3)
        yield from self.await_run_code_action(code_action)
        # yield from self.await_message('codeAction/resolve')
        self.assertEqual(entire_content(self.view), 'c\nd')

    def test_does_not_apply_with_nonmatching_document_version(self) -> Generator:
        initial_content = 'a\nb'
        code_action = create_test_code_action(self.view, 0, [
            ("c", range_from_points(Point(0, 0), Point(0, 1))),
            ("d", range_from_points(Point(1, 0), Point(1, 1))),
        ])
        self.insert_characters(initial_content)
        yield from self.await_message("textDocument/didChange")
        yield from self.await_run_code_action(code_action)
        self.assertEqual(entire_content(self.view), initial_content)

    def test_runs_command_in_resolved_code_action(self) -> Generator:
        code_action = create_test_code_action2("dosomethinguseful", ["1", 0, {"hello": "there"}])
        resolved_code_action = deepcopy(code_action)
        resolved_code_action["edit"] = create_code_action_edit(self.view, 3, [
            ("c", range_from_points(Point(0, 0), Point(0, 1))),
            ("d", range_from_points(Point(1, 0), Point(1, 1))),
        ])
        self.set_response('codeAction/resolve', resolved_code_action)
        self.set_response('workspace/executeCommand', {"reply": "OK done"})
        self.insert_characters('a\nb')
        yield from self.await_message("textDocument/didChange")
        self.assertEqual(self.view.change_count(), 3)
        yield from self.await_run_code_action(code_action)
        yield from self.await_message('codeAction/resolve')
        params = yield from self.await_message('workspace/executeCommand')
        self.assertEqual(params, {"command": "dosomethinguseful", "arguments": ["1", 0, {"hello": "there"}]})
        self.assertEqual(entire_content(self.view), 'c\nd')

    # Keep this test last as it breaks pyls!
    def test_applies_correctly_after_emoji(self) -> Generator:
        self.insert_characters('🕵️hi')
        yield from self.await_message("textDocument/didChange")
        code_action = create_test_code_action(self.view, self.view.change_count(), [
            ("bye", range_from_points(Point(0, 3), Point(0, 5))),
        ])
        yield from self.await_run_code_action(code_action)
        self.assertEqual(entire_content(self.view), '🕵️bye')

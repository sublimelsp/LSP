from copy import deepcopy
from LSP.plugin.code_actions import actions_manager
from LSP.plugin.code_actions import CodeActionsByConfigName
from LSP.plugin.code_actions import get_matching_kinds
from LSP.plugin.code_actions import run_code_action_or_command
from LSP.plugin.core.protocol import Point, Range
from LSP.plugin.core.typing import Any, Dict, Generator, List, Tuple
from LSP.plugin.core.url import filename_to_uri
from LSP.plugin.core.views import entire_content
from LSP.plugin.diagnostics import filter_by_point
from LSP.plugin.diagnostics import view_diagnostics
from LSP.plugin.documents import DocumentSyncListener
from setup import TextDocumentTestCase
from test_single_document import TEST_FILE_PATH
import unittest

TEST_FILE_URI = filename_to_uri(TEST_FILE_PATH)


def create_test_code_action(document_version: int, edits: List[Tuple[str, Range]], kind: str = None) -> Dict:
    def edit_to_lsp(edit: Tuple[str, Range]) -> Dict:
        new_text, range = edit
        return {
            "newText": new_text,
            "range": range.to_lsp()
        }
    action = {
        "title": "Fix errors",
        "edit": {
            "documentChanges": [
                {
                    "textDocument": {
                        "uri": TEST_FILE_URI,
                        "version": document_version
                    },
                    "edits": list(map(edit_to_lsp, edits))
                }
            ]
        }
    }
    if kind:
        action['kind'] = kind
    return action


def create_test_diagnostics(diagnostics: List[Tuple[str, Range]]) -> Dict:
    def diagnostic_to_lsp(diagnostic: Tuple[str, Range]) -> Dict:
        message, range = diagnostic
        return {
            "message": message,
            "range": range.to_lsp()
        }
    return {
        "uri": TEST_FILE_URI,
        "diagnostics": list(map(diagnostic_to_lsp, diagnostics))
    }


class CodeActionsOnSaveTestCase(TextDocumentTestCase):
    def setUp(self) -> Generator:
        yield from super().setUp()
        # "quickfix" is not supported but its here for testing purposes
        self.view.settings().set('lsp_code_actions_on_save', {'source.fixAll': True, 'quickfix': True})

    def tearDown(self) -> Generator:
        yield from self.await_clear_view_and_save()
        self.view.settings().set('lsp_code_actions_on_save', {})
        yield from super().tearDown()

    def get_test_server_capabilities(self) -> dict:
        capabilities = deepcopy(super().get_test_server_capabilities())
        capabilities['capabilities']['codeActionProvider'] = {'codeActionKinds': ['quickfix', 'source.fixAll']}
        return capabilities

    def test_applies_matching_kind(self) -> Generator:
        yield from self._setup_document_with_missing_semicolon()
        code_action_kind = 'source.fixAll'
        code_action = create_test_code_action(
            self.view.change_count(),
            [(';', Range(Point(0, 11), Point(0, 11)))],
            code_action_kind
        )
        self.set_response('textDocument/codeAction', [code_action])
        self.view.run_command('lsp_save')
        yield from self.await_message('textDocument/codeAction')
        self.assertEquals(entire_content(self.view), 'const x = 1;')
        self.assertEquals(self.view.is_dirty(), False)

    def test_applies_in_two_iterations(self) -> Generator:
        yield from self._setup_document_with_missing_semicolon()
        code_action_kind = 'source.fixAll'
        initial_change_count = self.view.change_count()
        yield from self.set_responses([
            (
                'textDocument/codeAction',
                [
                    create_test_code_action(
                        initial_change_count,
                        [(';', Range(Point(0, 11), Point(0, 11)))],
                        code_action_kind
                    )
                ]
            ),
            (
                'textDocument/codeAction',
                [
                    create_test_code_action(
                        initial_change_count + 1,
                        [('\nAnd again!', Range(Point(0, 12), Point(0, 12)))],
                        code_action_kind
                    )
                ]
            ),
        ])
        self.view.run_command('lsp_save')
        yield from self.await_message('textDocument/codeAction')
        yield from self.await_message('textDocument/codeAction')
        self.assertEquals(entire_content(self.view), 'const x = 1;\nAnd again!')
        self.assertEquals(self.view.is_dirty(), False)

    def test_applies_immediately_after_text_change(self) -> Generator:
        self.insert_characters('const x = 1')
        code_action_kind = 'source.fixAll'
        code_action = create_test_code_action(
            self.view.change_count(),
            [(';', Range(Point(0, 11), Point(0, 11)))],
            code_action_kind
        )
        self.set_response('textDocument/codeAction', [code_action])
        self.view.run_command('lsp_save')
        yield from self.await_message('textDocument/codeAction')
        self.assertEquals(entire_content(self.view), 'const x = 1;')
        self.assertEquals(self.view.is_dirty(), False)

    def test_no_fix_on_non_matching_kind(self) -> Generator:
        yield from self._setup_document_with_missing_semicolon()
        initial_content = 'const x = 1'
        self.view.run_command('lsp_save')
        self.assertEquals(entire_content(self.view), initial_content)
        yield lambda: not self.view.is_dirty()

    def test_does_not_apply_unsupported_kind(self) -> Generator:
        yield from self._setup_document_with_missing_semicolon()
        code_action_kind = 'quickfix'
        code_action = create_test_code_action(
            self.view.change_count(),
            [(';', Range(Point(0, 11), Point(0, 11)))],
            code_action_kind
        )
        self.set_response('textDocument/codeAction', [code_action])
        self.view.run_command('lsp_save')
        self.assertEquals(entire_content(self.view), 'const x = 1')

    def _setup_document_with_missing_semicolon(self) -> Generator:
        self.insert_characters('const x = 1')
        yield from self.await_message("textDocument/didChange")
        yield from self.await_client_notification(
            "textDocument/publishDiagnostics",
            create_test_diagnostics([
                ('Missing semicolon', Range(Point(0, 11), Point(0, 11))),
            ])
        )


class CodeActionMatchingTestCase(unittest.TestCase):
    def test_does_not_match(self) -> None:
        actual = get_matching_kinds({'a.x': True}, ['a.b'])
        expected = []  # type: List[str]
        self.assertEquals(actual, expected)

    def test_matches_exact_action(self) -> None:
        actual = get_matching_kinds({'a.b': True}, ['a.b'])
        expected = ['a.b']
        self.assertEquals(actual, expected)

    def test_matches_more_specific_action(self) -> None:
        actual = get_matching_kinds({'a.b': True}, ['a.b.c'])
        expected = ['a.b.c']
        self.assertEquals(actual, expected)

    def test_does_not_match_disabled_action(self) -> None:
        actual = get_matching_kinds({'a.b': True, 'a.b.c': False}, ['a.b.c'])
        expected = []  # type: List[str]
        self.assertEquals(actual, expected)


class CodeActionsListenerTestCase(TextDocumentTestCase):
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.original_debounce_time = DocumentSyncListener.code_actions_debounce_time

    def setUp(self) -> Generator:
        yield from super().setUp()
        DocumentSyncListener.code_actions_debounce_time = 0

    def tearDown(self) -> Generator:
        DocumentSyncListener.code_actions_debounce_time = self.original_debounce_time
        yield from super().tearDown()

    def get_test_server_capabilities(self) -> dict:
        capabilities = deepcopy(super().get_test_server_capabilities())
        capabilities['capabilities']['codeActionProvider'] = {}
        return capabilities

    def test_requests_with_diagnostics(self) -> Generator:
        initial_content = 'a\nb\nc'
        self.insert_characters(initial_content)
        yield from self.await_message('textDocument/didChange')
        range_a = Range(Point(0, 0), Point(0, 1))
        range_b = Range(Point(1, 0), Point(1, 1))
        range_c = Range(Point(2, 0), Point(2, 1))
        yield from self.await_client_notification(
            "textDocument/publishDiagnostics",
            create_test_diagnostics([('issue a', range_a), ('issue b', range_b), ('issue c', range_c)])
        )
        code_action_a = create_test_code_action(self.view.change_count(), [("A", range_a)])
        code_action_b = create_test_code_action(self.view.change_count(), [("B", range_b)])
        self.set_response('textDocument/codeAction', [code_action_a, code_action_b])
        self.view.run_command('lsp_selection_set', {"regions": [(0, 3)]})  # Select a and b.
        yield 100
        params = yield from self.await_message('textDocument/codeAction')
        self.assertEquals(params['range']['start']['line'], 0)
        self.assertEquals(params['range']['start']['character'], 0)
        self.assertEquals(params['range']['end']['line'], 1)
        self.assertEquals(params['range']['end']['character'], 1)
        self.assertEquals(len(params['context']['diagnostics']), 2)
        annotations_range = self.view.get_regions(DocumentSyncListener.CODE_ACTIONS_KEY)
        self.assertEquals(len(annotations_range), 1)
        self.assertEquals(annotations_range[0].a, 3)
        self.assertEquals(annotations_range[0].b, 0)

    def test_requests_with_no_diagnostics(self) -> Generator:
        initial_content = 'a\nb\nc'
        self.insert_characters(initial_content)
        yield from self.await_message("textDocument/didChange")
        range_a = Range(Point(0, 0), Point(0, 1))
        range_b = Range(Point(1, 0), Point(1, 1))
        code_action1 = create_test_code_action(0, [("A", range_a)])
        code_action2 = create_test_code_action(0, [("B", range_b)])
        self.set_response('textDocument/codeAction', [code_action1, code_action2])
        self.view.run_command('lsp_selection_set', {"regions": [(0, 3)]})  # Select a and b.
        yield 100
        params = yield from self.await_message('textDocument/codeAction')
        self.assertEquals(params['range']['start']['line'], 0)
        self.assertEquals(params['range']['start']['character'], 0)
        self.assertEquals(params['range']['end']['line'], 1)
        self.assertEquals(params['range']['end']['character'], 1)
        self.assertEquals(len(params['context']['diagnostics']), 0)
        annotations_range = self.view.get_regions(DocumentSyncListener.CODE_ACTIONS_KEY)
        self.assertEquals(len(annotations_range), 1)
        self.assertEquals(annotations_range[0].a, 3)
        self.assertEquals(annotations_range[0].b, 0)

    def test_extends_range_to_include_diagnostics(self) -> Generator:
        def handle_response(actions_by_config: CodeActionsByConfigName) -> None:
            pass
        self.insert_characters('x diagnostic')
        yield from self.await_message("textDocument/didChange")
        yield from self.await_client_notification(
            "textDocument/publishDiagnostics",
            create_test_diagnostics([
                ('diagnostic word', Range(Point(0, 2), Point(0, 12))),
                ('all content', Range(Point(0, 0), Point(0, 12))),
            ])
        )
        self.view.run_command('lsp_selection_set', {"regions": [(0, 5)]})
        yield 100
        params = yield from self.await_message('textDocument/codeAction')
        # Range should be extended to include range of all intersecting diagnostics
        self.assertEquals(params['range']['start']['line'], 0)
        self.assertEquals(params['range']['start']['character'], 0)
        self.assertEquals(params['range']['end']['line'], 0)
        self.assertEquals(params['range']['end']['character'], 12)
        self.assertEquals(len(params['context']['diagnostics']), 2)


class CodeActionsTestCase(TextDocumentTestCase):
    def get_test_server_capabilities(self) -> dict:
        capabilities = deepcopy(super().get_test_server_capabilities())
        capabilities['capabilities']['codeActionProvider'] = {}
        return capabilities

    def test_requests_for_point(self) -> Generator:
        def handle_response(actions_by_config: CodeActionsByConfigName) -> None:
            pass
        self.insert_characters('a\nb')
        yield from self.await_message("textDocument/didChange")
        yield from self.await_client_notification(
            "textDocument/publishDiagnostics",
            create_test_diagnostics([
                ('issue a', Range(Point(0, 0), Point(0, 1))),
                ('issue b', Range(Point(1, 0), Point(1, 1)))
            ])
        )
        diagnostics, extended_range = filter_by_point(view_diagnostics(self.view), Point(0, 0))
        actions_manager.request_with_diagnostics(self.view, extended_range, diagnostics, handle_response)
        params = yield from self.await_message('textDocument/codeAction')
        self.assertEquals(params['range']['start']['line'], 0)
        self.assertEquals(params['range']['start']['character'], 0)
        self.assertEquals(params['range']['end']['line'], 0)
        self.assertEquals(params['range']['end']['character'], 1)
        self.assertEquals(len(params['context']['diagnostics']), 1)

    def test_applies_code_actions(self) -> Generator:
        self.insert_characters('a\nb')
        yield from self.await_message("textDocument/didChange")
        code_action = create_test_code_action(self.view.change_count(), [
            ("c", Range(Point(0, 0), Point(0, 1))),
            ("d", Range(Point(1, 0), Point(1, 1))),
        ])
        run_code_action_or_command(self.view, self.config.name, code_action)
        self.assertEquals(entire_content(self.view), 'c\nd')

    def test_does_not_apply_with_nonmatching_document_version(self) -> Generator:
        initial_content = 'a\nb'
        self.insert_characters(initial_content)
        yield from self.await_message("textDocument/didChange")
        code_action = create_test_code_action(0, [
            ("c", Range(Point(0, 0), Point(0, 1))),
            ("d", Range(Point(1, 0), Point(1, 1))),
        ])
        run_code_action_or_command(self.view, self.config.name, code_action)
        self.assertEquals(entire_content(self.view), initial_content)

    # Keep this test last as it breaks pyls!
    def test_applies_correctly_after_emoji(self) -> Generator:
        self.insert_characters('🕵️hi')
        yield from self.await_message("textDocument/didChange")
        code_action = create_test_code_action(self.view.change_count(), [
            ("bye", Range(Point(0, 3), Point(0, 5))),
        ])
        run_code_action_or_command(self.view, self.config.name, code_action)
        self.assertEquals(entire_content(self.view), '🕵️bye')

from copy import deepcopy
from LSP.plugin.code_actions import get_matching_kinds
from LSP.plugin.core.protocol import Point, Range
from LSP.plugin.core.typing import Any, Dict, Generator, List, Tuple, Optional
from LSP.plugin.core.url import filename_to_uri
from LSP.plugin.core.views import entire_content
from LSP.plugin.documents import DocumentSyncListener
from LSP.plugin.session_view import SessionView
from LSP.plugin.core.views import versioned_text_document_identifier
from setup import TextDocumentTestCase
from test_single_document import TEST_FILE_PATH
import unittest
import sublime

TEST_FILE_URI = filename_to_uri(TEST_FILE_PATH)


def edit_to_lsp(edit: Tuple[str, Range]) -> Dict[str, Any]:
    return {"newText": edit[0], "range": edit[1].to_lsp()}


def create_code_action_edit(view: sublime.View, version: int, edits: List[Tuple[str, Range]]) -> Dict[str, Any]:
    return {
        "documentChanges": [
            {
                "textDocument": versioned_text_document_identifier(view, version),
                "edits": list(map(edit_to_lsp, edits))
            }
        ]
    }


def create_command(command_name: str, command_args: Optional[List[Any]] = None) -> Dict[str, Any]:
    result = {"command": command_name}  # type: Dict[str, Any]
    if command_args is not None:
        result["arguments"] = command_args
    return result


def create_test_code_action(view: sublime.View, version: int, edits: List[Tuple[str, Range]],
                            kind: str = None) -> Dict[str, Any]:
    action = {
        "title": "Fix errors",
        "edit": create_code_action_edit(view, version, edits)
    }
    if kind:
        action['kind'] = kind
    return action


def create_test_code_action2(command_name: str, command_args: Optional[List[Any]] = None,
                             kind: str = None) -> Dict[str, Any]:
    action = {
        "title": "Fix errors",
        "command": create_command(command_name, command_args)
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
            [(';', Range(Point(0, 11), Point(0, 11)))],
            code_action_kind
        )
        self.set_response('textDocument/codeAction', [code_action])
        self.view.run_command('lsp_save')
        yield from self.await_message('textDocument/codeAction')
        yield from self.await_message('textDocument/didSave')
        self.assertEquals(entire_content(self.view), 'const x = 1;')
        self.assertEquals(self.view.is_dirty(), False)

    def test_requests_with_diagnostics(self) -> Generator:
        yield from self._setup_document_with_missing_semicolon()
        code_action_kind = 'source.fixAll'
        code_action = create_test_code_action(
            self.view,
            self.view.change_count(),
            [(';', Range(Point(0, 11), Point(0, 11)))],
            code_action_kind
        )
        self.set_response('textDocument/codeAction', [code_action])
        self.view.run_command('lsp_save')
        code_action_request = yield from self.await_message('textDocument/codeAction')
        self.assertEquals(len(code_action_request['context']['diagnostics']), 1)
        self.assertEquals(code_action_request['context']['diagnostics'][0]['message'], 'Missing semicolon')
        yield from self.await_message('textDocument/didSave')
        self.assertEquals(entire_content(self.view), 'const x = 1;')
        self.assertEquals(self.view.is_dirty(), False)

    def test_applies_in_two_iterations(self) -> Generator:
        self.insert_characters('const x = 1')
        initial_change_count = self.view.change_count()
        yield from self.await_client_notification(
            "textDocument/publishDiagnostics",
            create_test_diagnostics([
                ('Missing semicolon', Range(Point(0, 11), Point(0, 11))),
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
                        [(';', Range(Point(0, 11), Point(0, 11)))],
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
                        [('\nAnd again!', Range(Point(0, 12), Point(0, 12)))],
                        code_action_kind
                    )
                ]
            ),
        ])
        self.view.run_command('lsp_save')
        # Wait for the view to be saved
        yield lambda: not self.view.is_dirty()
        self.assertEquals(entire_content(self.view), 'const x = 1;\nAnd again!')

    def test_applies_immediately_after_text_change(self) -> Generator:
        self.insert_characters('const x = 1')
        code_action_kind = 'source.fixAll'
        code_action = create_test_code_action(
            self.view,
            self.view.change_count(),
            [(';', Range(Point(0, 11), Point(0, 11)))],
            code_action_kind
        )
        self.set_response('textDocument/codeAction', [code_action])
        self.view.run_command('lsp_save')
        yield from self.await_message('textDocument/codeAction')
        yield from self.await_message('textDocument/didSave')
        self.assertEquals(entire_content(self.view), 'const x = 1;')
        self.assertEquals(self.view.is_dirty(), False)

    def test_no_fix_on_non_matching_kind(self) -> Generator:
        yield from self._setup_document_with_missing_semicolon()
        initial_content = 'const x = 1'
        self.view.run_command('lsp_save')
        yield from self.await_message('textDocument/didSave')
        self.assertEquals(entire_content(self.view), initial_content)
        self.assertEquals(self.view.is_dirty(), False)

    def test_does_not_apply_unsupported_kind(self) -> Generator:
        yield from self._setup_document_with_missing_semicolon()
        code_action_kind = 'quickfix'
        code_action = create_test_code_action(
            self.view,
            self.view.change_count(),
            [(';', Range(Point(0, 11), Point(0, 11)))],
            code_action_kind
        )
        self.set_response('textDocument/codeAction', [code_action])
        self.view.run_command('lsp_save')
        yield from self.await_message('textDocument/didSave')
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
    def setUp(self) -> Generator:
        yield from super().setUp()
        self.original_debounce_time = DocumentSyncListener.code_actions_debounce_time
        DocumentSyncListener.code_actions_debounce_time = 0

    def tearDown(self) -> None:
        DocumentSyncListener.code_actions_debounce_time = self.original_debounce_time
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
        range_a = Range(Point(0, 0), Point(0, 1))
        range_b = Range(Point(1, 0), Point(1, 1))
        range_c = Range(Point(2, 0), Point(2, 1))
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
        self.assertEquals(params['range']['start']['line'], 0)
        self.assertEquals(params['range']['start']['character'], 0)
        self.assertEquals(params['range']['end']['line'], 1)
        self.assertEquals(params['range']['end']['character'], 1)
        self.assertEquals(len(params['context']['diagnostics']), 2)
        annotations_range = self.view.get_regions(SessionView.CODE_ACTIONS_KEY)
        self.assertEquals(len(annotations_range), 1)
        self.assertEquals(annotations_range[0].a, 3)
        self.assertEquals(annotations_range[0].b, 0)

    def test_requests_with_no_diagnostics(self) -> Generator:
        initial_content = 'a\nb\nc'
        self.insert_characters(initial_content)
        yield from self.await_message("textDocument/didChange")
        range_a = Range(Point(0, 0), Point(0, 1))
        range_b = Range(Point(1, 0), Point(1, 1))
        code_action1 = create_test_code_action(self.view, 0, [("A", range_a)])
        code_action2 = create_test_code_action(self.view, 0, [("B", range_b)])
        self.set_response('textDocument/codeAction', [code_action1, code_action2])
        self.view.run_command('lsp_selection_set', {"regions": [(0, 3)]})  # Select a and b.
        yield 100
        params = yield from self.await_message('textDocument/codeAction')
        self.assertEquals(params['range']['start']['line'], 0)
        self.assertEquals(params['range']['start']['character'], 0)
        self.assertEquals(params['range']['end']['line'], 1)
        self.assertEquals(params['range']['end']['character'], 1)
        self.assertEquals(len(params['context']['diagnostics']), 0)
        annotations_range = self.view.get_regions(SessionView.CODE_ACTIONS_KEY)
        self.assertEquals(len(annotations_range), 1)
        self.assertEquals(annotations_range[0].a, 3)
        self.assertEquals(annotations_range[0].b, 0)

    def test_extends_range_to_include_diagnostics(self) -> Generator:
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
                ('issue a', Range(Point(0, 0), Point(0, 1))),
                ('issue b', Range(Point(1, 0), Point(1, 1)))
            ])
        )
        params = yield from self.await_message('textDocument/codeAction')
        self.assertEquals(params['range']['start']['line'], 1)
        self.assertEquals(params['range']['start']['character'], 0)
        self.assertEquals(params['range']['end']['line'], 1)
        self.assertEquals(params['range']['end']['character'], 1)
        self.assertEquals(len(params['context']['diagnostics']), 1)

    def test_applies_code_action_with_matching_document_version(self) -> Generator:
        code_action = create_test_code_action(self.view, 3, [
            ("c", Range(Point(0, 0), Point(0, 1))),
            ("d", Range(Point(1, 0), Point(1, 1))),
        ])
        self.insert_characters('a\nb')
        yield from self.await_message("textDocument/didChange")
        self.assertEqual(self.view.change_count(), 3)
        yield from self.await_run_code_action(code_action)
        # yield from self.await_message('codeAction/resolve')
        self.assertEquals(entire_content(self.view), 'c\nd')

    def test_does_not_apply_with_nonmatching_document_version(self) -> Generator:
        initial_content = 'a\nb'
        code_action = create_test_code_action(self.view, 0, [
            ("c", Range(Point(0, 0), Point(0, 1))),
            ("d", Range(Point(1, 0), Point(1, 1))),
        ])
        self.insert_characters(initial_content)
        yield from self.await_message("textDocument/didChange")
        yield from self.await_run_code_action(code_action)
        self.assertEquals(entire_content(self.view), initial_content)

    def test_runs_command_in_resolved_code_action(self) -> Generator:
        code_action = create_test_code_action2("dosomethinguseful", ["1", 0, {"hello": "there"}])
        resolved_code_action = deepcopy(code_action)
        resolved_code_action["edit"] = create_code_action_edit(self.view, 3, [
            ("c", Range(Point(0, 0), Point(0, 1))),
            ("d", Range(Point(1, 0), Point(1, 1))),
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
        self.assertEquals(entire_content(self.view), 'c\nd')

    # Keep this test last as it breaks pyls!
    def test_applies_correctly_after_emoji(self) -> Generator:
        self.insert_characters('🕵️hi')
        yield from self.await_message("textDocument/didChange")
        code_action = create_test_code_action(self.view, self.view.change_count(), [
            ("bye", Range(Point(0, 3), Point(0, 5))),
        ])
        yield from self.await_run_code_action(code_action)
        self.assertEquals(entire_content(self.view), '🕵️bye')

from __future__ import annotations

from .setup import TextDocumentTestCase
from .test_single_document import TEST_FILE_PATH
from copy import deepcopy
from LSP.plugin.code_actions import CodeActionsOnFormatOnSaveTask
from LSP.plugin.code_actions import CodeActionsOnSaveTask
from LSP.plugin.code_actions import get_matching_kinds
from LSP.plugin.core.constants import RegionKey
from LSP.plugin.core.protocol import Point
from LSP.plugin.core.settings import userprefs
from LSP.plugin.core.url import filename_to_uri
from LSP.plugin.core.views import entire_content
from LSP.plugin.core.views import kind_contains_other_kind
from LSP.plugin.core.views import versioned_text_document_identifier
from LSP.plugin.documents import DocumentSyncListener
from typing import TYPE_CHECKING
import unittest

if TYPE_CHECKING:
    from LSP.protocol import CodeAction
    from LSP.protocol import Command
    from LSP.protocol import Range
    from LSP.protocol import TextEdit
    from LSP.protocol import WorkspaceEdit
    from typing import Any
    import sublime

TEST_FILE_URI = filename_to_uri(TEST_FILE_PATH)


def edit_to_lsp(edit: tuple[str, Range]) -> TextEdit:
    return {"newText": edit[0], "range": edit[1]}


def range_from_points(start: Point, end: Point) -> Range:
    return {
        'start': start.to_lsp(),
        'end': end.to_lsp()
    }


def create_code_action_edit(view: sublime.View, version: int, edits: list[tuple[str, Range]]) -> WorkspaceEdit:
    return {
        "documentChanges": [
            {
                "textDocument": versioned_text_document_identifier(view, version),
                "edits": list(map(edit_to_lsp, edits))
            }
        ]
    }


def create_command(command_name: str, command_args: list[Any] | None = None) -> Command:
    result: Command = {"command": command_name}
    if command_args is not None:
        result["arguments"] = command_args
    return result


def create_test_code_action(view: sublime.View, version: int, edits: list[tuple[str, Range]],
                            kind: str | None = None) -> CodeAction:
    action: CodeAction = {
        "title": "Fix errors",
        "edit": create_code_action_edit(view, version, edits)
    }
    if kind:
        action['kind'] = kind
    return action


def create_test_code_action2(command_name: str, command_args: list[Any] | None = None,
                             kind: str | None = None) -> CodeAction:
    action: CodeAction = {
        "title": "Fix errors",
        "command": create_command(command_name, command_args)
    }
    if kind:
        action['kind'] = kind
    return action


def create_disabled_code_action(view: sublime.View, version: int, edits: list[tuple[str, Range]]) -> dict[str, Any]:
    return {
        "title": "Fix errors",
        "edit": create_code_action_edit(view, version, edits),
        "disabled": {
            "reason": "Do not use"
        },
    }


def create_test_diagnostics(diagnostics: list[tuple[str, Range]]) -> dict:
    def diagnostic_to_lsp(diagnostic: tuple[str, Range]) -> dict:
        message, lsp_range = diagnostic
        return {
            "message": message,
            "range": lsp_range
        }
    return {
        "uri": TEST_FILE_URI,
        "diagnostics": list(map(diagnostic_to_lsp, diagnostics))
    }


class CodeActionsTestCaseBase(TextDocumentTestCase):
    def init_view_settings(self) -> None:
        super().init_view_settings()
        # "quickfix" is not supported but its here for testing purposes
        self.view.settings().set('lsp_code_actions_on_save', {'source.fixAll': True, 'quickfix': True})
        self.view.settings().set("lsp_format_on_save", False)

    @classmethod
    def get_test_server_capabilities(cls) -> dict:
        capabilities = deepcopy(super().get_test_server_capabilities())
        capabilities['capabilities']['codeActionProvider'] = {'codeActionKinds': ['quickfix', 'source.fixAll']}
        return capabilities

    async def tearDown(self) -> None:
        await self.await_clear_view_and_save()
        await super().tearDown()


class CodeActionsOnSaveTaskTestCase(TextDocumentTestCase):
    def init_view_settings(self) -> None:
        super().init_view_settings()
        self.view.settings().set('lsp_code_actions_on_save', {"source.fixAll": True})
        self.view.settings().set('lsp_code_actions_on_format', {"source.fixAll.eslint": True})
        self.view.settings().set('lsp_format_on_save', False)

    def test_applicable_when_format_on_save_disabled(self) -> None:
        self.assertTrue(CodeActionsOnSaveTask.is_applicable(self.view))

    def test_applicable_when_format_on_save_enabled(self) -> None:
        self.view.settings().set('lsp_format_on_save', True)
        self.assertFalse(CodeActionsOnSaveTask.is_applicable(self.view))


class CodeActionsOnSaveTestCase(CodeActionsTestCaseBase):
    async def test_applies_matching_kind(self) -> None:

        # Set up the mock.
        await self._setup_document_with_missing_semicolon()
        code_action_kind = 'source.fixAll'
        code_action = create_test_code_action(
            self.view,
            self.view.change_count(),
            [(';', range_from_points(Point(0, 11), Point(0, 11)))],
            code_action_kind
        )
        await self.mock_response('textDocument/codeAction', [code_action])

        # Save the file.
        self.view.run_command('lsp_save', {'async': True})

        # The save should have caused a request for code actions.
        await self.await_message('textDocument/codeAction')

        # And it should have caused a didSave notification.
        await self.await_message('textDocument/didSave')

        # After the didSave, the view should not be dirty (clean?)
        self.assertEqual(self.view.is_dirty(), False)

        # The mocked code action should have been applied.
        self.assertEqual(entire_content(self.view), 'const x = 1;')

    async def test_requests_with_diagnostics(self) -> None:
        await self._setup_document_with_missing_semicolon()
        code_action_kind = 'source.fixAll'
        code_action = create_test_code_action(
            self.view,
            self.view.change_count(),
            [(';', range_from_points(Point(0, 11), Point(0, 11)))],
            code_action_kind
        )
        await self.mock_response('textDocument/codeAction', [code_action])
        self.view.run_command('lsp_save', {'async': True})
        code_action_request = await self.await_message('textDocument/codeAction')
        self.assertIsInstance(code_action_request, dict)
        assert isinstance(code_action_request, dict)
        self.assertEqual(len(code_action_request['context']['diagnostics']), 1)
        self.assertEqual(code_action_request['context']['diagnostics'][0]['message'], 'Missing semicolon')
        await self.await_message('textDocument/didSave')
        self.assertEqual(entire_content(self.view), 'const x = 1;')
        self.assertEqual(self.view.is_dirty(), False)

    async def test_applies_only_one_pass(self) -> None:
        self.insert_characters('const x = 1')
        initial_change_count = self.view.change_count()
        await self.mock_client_notification(
            "textDocument/publishDiagnostics",
            create_test_diagnostics([
                ('Missing semicolon', range_from_points(Point(0, 11), Point(0, 11))),
            ])
        )
        code_action_kind = 'source.fixAll'
        await self.mock_responses([
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
        await self.wait_until_st_state(lambda: not self.view.is_dirty())
        self.assertEqual(entire_content(self.view), 'const x = 1;')

    async def test_applies_immediately_after_text_change(self) -> None:
        self.insert_characters('const x = 1')
        code_action_kind = 'source.fixAll'
        code_action = create_test_code_action(
            self.view,
            self.view.change_count(),
            [(';', range_from_points(Point(0, 11), Point(0, 11)))],
            code_action_kind
        )
        await self.mock_response('textDocument/codeAction', [code_action])
        self.view.run_command('lsp_save', {'async': True})
        await self.await_message('textDocument/codeAction')
        await self.await_message('textDocument/didSave')
        self.assertEqual(entire_content(self.view), 'const x = 1;')
        self.assertEqual(self.view.is_dirty(), False)

    async def test_no_fix_on_non_matching_kind(self) -> None:
        await self._setup_document_with_missing_semicolon()
        initial_content = 'const x = 1'
        self.view.run_command('lsp_save', {'async': True})
        await self.await_message('textDocument/didSave')
        self.assertEqual(entire_content(self.view), initial_content)
        self.assertEqual(self.view.is_dirty(), False)

    async def test_does_not_apply_unsupported_kind(self) -> None:
        await self._setup_document_with_missing_semicolon()
        code_action_kind = 'quickfix'
        code_action = create_test_code_action(
            self.view,
            self.view.change_count(),
            [(';', range_from_points(Point(0, 11), Point(0, 11)))],
            code_action_kind
        )
        await self.mock_response('textDocument/codeAction', [code_action])
        self.view.run_command('lsp_save', {'async': True})
        await self.await_message('textDocument/didSave')
        self.assertEqual(entire_content(self.view), 'const x = 1')

    async def _setup_document_with_missing_semicolon(self) -> None:
        self.insert_characters('const x = 1')
        await self.await_message("textDocument/didChange")
        await self.mock_client_notification(
            "textDocument/publishDiagnostics",
            create_test_diagnostics([
                ('Missing semicolon', range_from_points(Point(0, 11), Point(0, 11))),
            ])
        )


class CodeActionsOnFormatTestCase(CodeActionsTestCaseBase):
    def init_view_settings(self) -> None:
        super().init_view_settings()
        self.view.settings().set('lsp_code_actions_on_format', {'source.fixAll': True, 'quickfix': True})

    async def test_format_document_with_code_actions_on_format(self) -> None:
        self.insert_characters(' const x = 1')
        await self.await_message('textDocument/didChange')

        code_action_kind = 'source.fixAll'
        code_action = create_test_code_action(
            self.view,
            self.view.change_count(),
            [(';', range_from_points(Point(0, 12), Point(0, 12)))],
            code_action_kind
        )
        await self.mock_response('textDocument/codeAction', [code_action])

        await self.mock_response('textDocument/formatting', [{
            'newText': "",
            'range': {
                'start': {'line': 0, 'character': 0},
                'end': {'line': 0, 'character': 1}
            }
        }])

        self.view.run_command('lsp_format_document', {'async': True})
        await self.await_message('textDocument/codeAction')
        await self.await_message('textDocument/formatting')
        await self.await_message('textDocument/didChange')
        # Response is fixed (fixAll added ";") and formatted (removed leading space)
        self.assertEqual(entire_content(self.view), 'const x = 1;')
        # Formatting does not save the document
        self.assertEqual(self.view.is_dirty(), True)

    async def test_format_on_save_with_code_actions_on_format(self) -> None:
        self.view.settings().set("lsp_format_on_save", True)
        self.insert_characters(' const x = 1')
        await self.await_message("textDocument/didChange")

        code_action_kind = 'source.fixAll'
        code_action = create_test_code_action(
            self.view,
            self.view.change_count(),
            [(';', range_from_points(Point(0, 12), Point(0, 12)))],
            code_action_kind
        )
        await self.mock_response('textDocument/codeAction', [code_action])

        await self.mock_response('textDocument/formatting', [{
            'newText': "",
            'range': {
                'start': {'line': 0, 'character': 0},
                'end': {'line': 0, 'character': 1}
            }
        }])

        self.view.run_command("lsp_save", {'async': True})
        await self.await_message('textDocument/codeAction')
        await self.await_message('textDocument/formatting')
        await self.await_message('textDocument/didChange')
        await self.await_message('textDocument/didSave')
        # Response is fixed (fixAll added ";") and formatted (removed leading space)
        self.assertEqual(entire_content(self.view), 'const x = 1;')
        # Document should be saved
        self.assertEqual(self.view.is_dirty(), False)


class CodeActionsOnFormatOnSaveTaskTestCase(TextDocumentTestCase):
    def init_view_settings(self) -> None:
        super().init_view_settings()
        self.view.settings().set('lsp_code_actions_on_save', {'source.fixAll': True, 'quickfix': True})
        self.view.settings().set('lsp_code_actions_on_format', {})
        self.view.settings().set("lsp_format_on_save", False)
        userprefs().lsp_format_on_save = False
        userprefs().lsp_code_actions_on_save = {}
        userprefs().lsp_code_actions_on_format = {}

    def test_code_actions_format_on_save_task_enabled__unset(self) -> None:
        self.view.settings().set('lsp_code_actions_on_format', {})
        self.view.settings().set("lsp_format_on_save", False)
        self.assertFalse(CodeActionsOnFormatOnSaveTask.is_applicable(self.view))

    def test_code_actions_format_on_save_task_enabled__format_on_save_false(self) -> None:
        self.view.settings().set('lsp_code_actions_on_format', {"source.fixAll": True})
        self.view.settings().set("lsp_format_on_save", False)
        self.assertFalse(CodeActionsOnFormatOnSaveTask.is_applicable(self.view))

    def test_code_actions_format_on_save_task_enabled__unsupported(self) -> None:
        self.view.settings().set('lsp_code_actions_on_save', {})
        self.view.settings().set('lsp_code_actions_on_format', {"quickfix.unsupported": True})
        self.view.settings().set("lsp_format_on_save", True)
        self.assertFalse(CodeActionsOnFormatOnSaveTask.is_applicable(self.view))

    def test_code_actions_format_on_save_task_enabled__standard_settings(self) -> None:
        self.view.settings().set('lsp_code_actions_on_format', {"source.fixAll": True})
        self.view.settings().set("lsp_format_on_save", True)
        self.assertTrue(CodeActionsOnFormatOnSaveTask.is_applicable(self.view))

    def test_code_actions_format_on_save_task_enabled__user_settings(self) -> None:
        self.view.settings().set('lsp_code_actions_on_format', {"source.fixAll": True})
        userprefs().lsp_format_on_save = False
        del self.view.settings()["lsp_format_on_save"]
        self.assertFalse(CodeActionsOnFormatOnSaveTask.is_applicable(self.view))
        userprefs().lsp_format_on_save = True
        self.assertTrue(CodeActionsOnFormatOnSaveTask.is_applicable(self.view))

    def test_code_actions_format_on_save_task_get_code_actions__settings_are_merged(self) -> None:
        self.view.settings().set('lsp_code_actions_on_save', {"source.fixAll": True, "source.organizeImports": True})
        self.view.settings().set('lsp_code_actions_on_format', {"source.fixAll": False, "source.sort.json": False})
        # Actions defined in both settings are merged. When a duplicate action is found it will be True (enabled)
        # when enabled in lsp_code_actions_on_save or lsp_code_actions_on_format
        self.assertEqual(
            CodeActionsOnFormatOnSaveTask.get_code_action_kinds(view=self.view),
            {"source.fixAll": True, "source.organizeImports": True, "source.sort.json": False},
        )


class CodeActionMatchingTestCase(unittest.TestCase):
    def test_does_not_match(self) -> None:
        actual = get_matching_kinds({'a.x': True}, ['a.b'])
        expected: list[str] = []
        self.assertEqual(actual, expected)

    def test_matches_exact_action(self) -> None:
        actual = get_matching_kinds({'a.b': True}, ['a.b'])
        expected = ['a.b']
        self.assertEqual(actual, expected)

    def test_matches_more_specific_action(self) -> None:
        actual = get_matching_kinds({'a.b': True}, ['a.b.c'])
        expected = ['a.b.c']
        self.assertEqual(actual, expected)

    def test_matches_multiple_specific_actions(self) -> None:
        actual = get_matching_kinds({'a.b': True, 'a.b.c': True}, ['a.b.c', 'a.b.d'])
        expected = ['a.b.c', 'a.b.d']
        self.assertEqual(actual, expected)

    def test_does_not_match_disabled_action(self) -> None:
        actual = get_matching_kinds({'a.b': True, 'a.b.c': False}, ['a.b.c'])
        expected: list[str] = []
        self.assertEqual(actual, expected)

    def test_does_not_match_disabled_parent_action(self) -> None:
        actual = get_matching_kinds({'a.b': False, 'a.b.c': True}, ['a.b.c'])
        expected: list[str] = ['a.b.c']
        self.assertEqual(actual, expected)

    def test_kind_matching(self) -> None:
        # Positive
        self.assertTrue(kind_contains_other_kind('a', 'a.b'))
        self.assertTrue(kind_contains_other_kind('a.b', 'a.b'))
        # Negative
        self.assertFalse(kind_contains_other_kind('a', 'b.a'))
        self.assertFalse(kind_contains_other_kind('a.b', 'b'))
        self.assertFalse(kind_contains_other_kind('a.b', 'a'))
        self.assertFalse(kind_contains_other_kind('aa', 'a'))
        self.assertFalse(kind_contains_other_kind('aa.b', 'a'))
        self.assertFalse(kind_contains_other_kind('aa.b', 'b'))


class CodeActionsListenerTestCase(TextDocumentTestCase):
    async def setUp(self) -> None:
        await super().setUp()
        self.original_debounce_time = DocumentSyncListener.debounce_time
        DocumentSyncListener.debounce_time = 0

    async def tearDown(self) -> None:
        DocumentSyncListener.debounce_time = self.original_debounce_time
        await super().tearDown()

    @classmethod
    def get_test_server_capabilities(cls) -> dict:
        capabilities = deepcopy(super().get_test_server_capabilities())
        capabilities['capabilities']['codeActionProvider'] = {}
        return capabilities

    async def test_requests_with_diagnostics(self) -> None:
        # Setup the mock.
        initial_content = 'a\nb\nc'
        range_a = range_from_points(Point(0, 0), Point(0, 1))
        range_b = range_from_points(Point(1, 0), Point(1, 1))
        range_c = range_from_points(Point(2, 0), Point(2, 1))
        code_action_a = create_test_code_action(self.view, self.view.change_count(), [("A", range_a)])
        code_action_b = create_test_code_action(self.view, self.view.change_count(), [("B", range_b)])
        await self.mock_response('textDocument/codeAction', [code_action_a, code_action_b])

        # Insert:
        # a
        # b
        # c
        self.insert_characters(initial_content)
        await self.await_message('textDocument/didChange')

        # Select:
        # a
        # [b
        # c
        # ]
        self.view.run_command('lsp_selection_set', {"regions": [(0, 3)]})  # Select a and b.
        await self.wait_until_st_state(
            lambda: len(self.view.sel()) == 1 and self.view.sel()[0].a == 0 and self.view.sel()[0].b == 3
        )

        # Make fake server emit diagnostics.
        await self.mock_client_notification(
            "textDocument/publishDiagnostics",
            create_test_diagnostics([('issue a', range_a), ('issue b', range_b), ('issue c', range_c)])
        )

        # The fake diagnostics should have triggered a code actions request.
        params = await self.await_message('textDocument/codeAction')

        # Assert the parameters we set up in the mock response above.
        self.assertEqual(params['range']['start']['line'], 0)
        self.assertEqual(params['range']['start']['character'], 0)
        self.assertEqual(params['range']['end']['line'], 1)
        self.assertEqual(params['range']['end']['character'], 1)
        self.assertEqual(len(params['context']['diagnostics']), 2)
        annotations_range = self.view.get_regions(RegionKey.CODE_ACTION)
        self.assertEqual(len(annotations_range), 1)
        self.assertEqual(annotations_range[0].a, 3)
        self.assertEqual(annotations_range[0].b, 0)

    async def test_excludes_disabled_code_actions(self) -> None:
        initial_content = 'a\n'
        self.insert_characters(initial_content)
        await self.await_message("textDocument/didChange")
        range_a = range_from_points(Point(0, 0), Point(0, 1))
        await self.mock_client_notification(
            "textDocument/publishDiagnostics",
            create_test_diagnostics([('issue a', range_a)])
        )
        code_action = create_disabled_code_action(
            self.view,
            self.view.change_count(),
            [(';', range_a)]
        )
        await self.mock_response('textDocument/codeAction', [code_action])
        self.view.run_command('lsp_selection_set', {"regions": [(0, 1)]})  # Select a
        await self.await_message('textDocument/codeAction')
        code_action_ranges = self.view.get_regions(RegionKey.CODE_ACTION)
        self.assertEqual(len(code_action_ranges), 0)


class CodeActionsTestCase(TextDocumentTestCase):

    @classmethod
    def get_test_server_capabilities(cls) -> dict:
        capabilities = deepcopy(super().get_test_server_capabilities())
        capabilities['capabilities']['codeActionProvider'] = {"resolveProvider": True}
        return capabilities

    async def test_requests_code_actions_on_newly_published_diagnostics(self) -> None:
        self.insert_characters('a\nb')
        await self.await_message("textDocument/didChange")
        await self.mock_client_notification(
            "textDocument/publishDiagnostics",
            create_test_diagnostics([
                ('issue a', range_from_points(Point(0, 0), Point(0, 1))),
                ('issue b', range_from_points(Point(1, 0), Point(1, 1)))
            ])
        )
        params = await self.await_message('textDocument/codeAction')
        self.assertIsInstance(params, dict)
        assert isinstance(params, dict)
        self.assertEqual(params['range']['start']['line'], 1)
        self.assertEqual(params['range']['start']['character'], 1)
        self.assertEqual(params['range']['end']['line'], 1)
        self.assertEqual(params['range']['end']['character'], 1)
        self.assertEqual(len(params['context']['diagnostics']), 1)

    async def test_applies_code_action_with_matching_document_version(self) -> None:
        code_action = create_test_code_action(self.view, 3, [
            ("c", range_from_points(Point(0, 0), Point(0, 1))),
            ("d", range_from_points(Point(1, 0), Point(1, 1))),
        ])
        self.insert_characters('a\nb')
        await self.await_message("textDocument/didChange")
        self.assertEqual(self.view.change_count(), 3)
        await self.await_run_code_action(code_action)
        # await self.await_message('codeAction/resolve')
        self.assertEqual(entire_content(self.view), 'c\nd')

    async def test_does_not_apply_with_nonmatching_document_version(self) -> None:
        initial_content = 'a\nb'
        code_action = create_test_code_action(self.view, 0, [
            ("c", range_from_points(Point(0, 0), Point(0, 1))),
            ("d", range_from_points(Point(1, 0), Point(1, 1))),
        ])
        self.insert_characters(initial_content)
        await self.await_message("textDocument/didChange")
        await self.await_run_code_action(code_action)
        self.assertEqual(entire_content(self.view), initial_content)

    async def test_runs_command_in_resolved_code_action(self) -> None:
        code_action = create_test_code_action2("dosomethinguseful", ["1", 0, {"hello": "there"}])
        resolved_code_action = deepcopy(code_action)
        resolved_code_action["edit"] = create_code_action_edit(self.view, 3, [
            ("c", range_from_points(Point(0, 0), Point(0, 1))),
            ("d", range_from_points(Point(1, 0), Point(1, 1))),
        ])
        await self.mock_response('codeAction/resolve', resolved_code_action)
        await self.mock_response('workspace/executeCommand', {"reply": "OK done"})
        self.insert_characters('a\nb')
        await self.await_message("textDocument/didChange")
        self.assertEqual(self.view.change_count(), 3)
        await self.await_run_code_action(code_action)
        await self.await_message('codeAction/resolve')
        params = await self.await_message('workspace/executeCommand')
        self.assertEqual(params, {"command": "dosomethinguseful", "arguments": ["1", 0, {"hello": "there"}]})
        self.assertEqual(entire_content(self.view), 'c\nd')

    # Keep this test last as it breaks pyls!
    async def test_applies_correctly_after_emoji(self) -> None:
        self.insert_characters('🕵️hi')
        await self.await_message("textDocument/didChange")
        code_action = create_test_code_action(self.view, self.view.change_count(), [
            ("bye", range_from_points(Point(0, 3), Point(0, 5))),
        ])
        await self.await_run_code_action(code_action)
        self.assertEqual(entire_content(self.view), '🕵️bye')

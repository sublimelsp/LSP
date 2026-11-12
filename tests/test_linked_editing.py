from __future__ import annotations

from .setup import close_test_view
from .setup import TextDocumentTestCase
from copy import deepcopy
from LSP.plugin.core.aio import tick
from LSP.plugin.core.constants import RegionKey
from LSP.plugin.core.settings import userprefs
from typing import Any
from typing import Callable
from typing import TYPE_CHECKING
from typing_extensions import override
import sublime

if TYPE_CHECKING:
    from LSP.plugin.linked_editing import LinkedEditing


def make_range(start: int, end: int) -> dict[str, Any]:
    return {'start': {'line': 0, 'character': start}, 'end': {'line': 0, 'character': end}}


TAGS = "<div></div>"
TAG_RANGES = {'ranges': [make_range(1, 4), make_range(7, 10)]}


class LinkedEditingTestCaseBase(TextDocumentTestCase):

    @override
    @classmethod
    def get_test_server_capabilities(cls) -> dict:
        capabilities = deepcopy(super().get_test_server_capabilities())
        capabilities['capabilities']['linkedEditingRangeProvider'] = True
        return capabilities

    def get_linked_editing(self) -> LinkedEditing:
        listener = self.ensure_document_listener_created()
        assert listener
        return listener.linked_editing

    def text(self) -> str:
        return self.view.substr(sublime.Region(0, self.view.size()))

    def set_cursor(self, point: int) -> None:
        self.view.run_command("lsp_selection_set", {"regions": [(point, point)]})

    async def activate(
        self, point: int, response: dict[str, Any] | None = TAG_RANGES, *, expect_active: bool = True
    ) -> None:
        self.insert_characters(TAGS)
        await self.await_message("textDocument/didChange")
        self.set_cursor(point)
        await self.mock_response("textDocument/linkedEditingRange", response)
        self.linked_editing = self.get_linked_editing()
        await self.linked_editing.request(self.session, point, self.view.change_count())
        await self.await_message("textDocument/linkedEditingRange")
        if expect_active:
            await self.wait_until(self.linked_editing.is_active)

    async def activate_after_edit(self, point: int, edit: Callable[[], None]) -> None:
        """Request the ranges at the point, and make edits before the response is handled."""
        self.insert_characters(TAGS)
        await self.await_message("textDocument/didChange")
        self.set_cursor(point)
        await self.mock_response("textDocument/linkedEditingRange", TAG_RANGES)
        self.linked_editing = self.get_linked_editing()
        version = self.view.change_count()
        edit()
        await self.linked_editing.request(self.session, point, version)
        await self.await_message("textDocument/linkedEditingRange")

    async def wait_for_text(self, expected: str) -> None:
        await self.wait_until(lambda: self.text() == expected)

    def undo(self) -> None:
        """Undo like a key binding does, which makes the listeners see the undo command and the undo action."""
        listener = self.ensure_document_listener_created()
        assert listener

        def run() -> None:
            listener.on_text_command("undo", None)
            self.view.run_command("undo")

        sublime.set_timeout(run)

    def left_delete(self) -> None:
        """Delete like a key binding does, which makes the listener see the command after it ran."""
        listener = self.ensure_document_listener_created()
        assert listener

        def run() -> None:
            self.view.run_command("left_delete")
            listener.on_post_text_command("left_delete", None)

        sublime.set_timeout(run)


class LinkedEditingTestCase(LinkedEditingTestCaseBase):

    async def test_request_params(self) -> None:
        self.insert_characters(TAGS)
        await self.await_message("textDocument/didChange")
        await self.mock_response("textDocument/linkedEditingRange", TAG_RANGES)
        await self.get_linked_editing().request(self.session, 4, self.view.change_count())
        params = await self.await_message("textDocument/linkedEditingRange")
        self.assertEqual(params["position"], {"line": 0, "character": 4})

    async def test_capability(self) -> None:
        capabilities = self.initialize_params["capabilities"]["textDocument"]
        self.assertEqual(capabilities["linkedEditingRange"], {"dynamicRegistration": True})

    async def test_insert_at_end_of_opening_tag(self) -> None:
        await self.activate(4)
        self.insert_characters("x")
        await self.wait_for_text("<divx></divx>")
        self.insert_characters("y")
        await self.wait_for_text("<divxy></divxy>")
        self.assertEqual(self.linked_editing.ranges, (sublime.Region(1, 6), sublime.Region(9, 14)))
        self.assertEqual(self.view.get_regions(RegionKey.LINKED_EDITING), [sublime.Region(1, 6), sublime.Region(9, 14)])
        self.assertEqual(list(self.view.sel()), [sublime.Region(6, 6)])

    async def test_typing_before_response(self) -> None:
        await self.activate_after_edit(4, lambda: self.insert_characters("x"))
        await self.wait_for_text("<divx></divx>")
        self.assertEqual(self.linked_editing.ranges, (sublime.Region(1, 5), sublime.Region(8, 12)))
        self.insert_characters("y")
        await self.wait_for_text("<divxy></divxy>")

    async def test_typing_before_response_after_inserting_line(self) -> None:
        def edit() -> None:
            self.set_cursor(0)
            self.insert_characters("\n")
            self.set_cursor(5)
            self.insert_characters("x")

        await self.activate_after_edit(4, edit)
        await self.wait_for_text("\n<divx></divx>")
        self.assertEqual(self.linked_editing.ranges, (sublime.Region(2, 6), sublime.Region(9, 13)))

    async def test_typing_space_before_response(self) -> None:
        await self.activate_after_edit(4, lambda: self.insert_characters(" "))
        self.assertEqual(self.text(), "<div ></div>")
        self.assertFalse(self.linked_editing.is_active())

    async def test_edit_overlapping_range_before_response(self) -> None:
        def edit() -> None:
            self.view.run_command("lsp_selection_set", {"regions": [(3, 6)]})
            self.insert_characters("x")

        await self.activate_after_edit(4, edit)
        self.assertEqual(self.text(), "<dix/div>")
        self.assertFalse(self.linked_editing.is_active())

    async def test_undo_before_response(self) -> None:
        listener = self.ensure_document_listener_created()
        assert listener

        def edit() -> None:
            self.insert_characters("x")
            listener.on_text_command("undo", None)
            self.view.run_command("undo")

        await self.activate_after_edit(4, edit)
        self.assertEqual(self.text(), TAGS)
        self.assertFalse(self.linked_editing.is_active())

    async def test_ranges_are_drawn(self) -> None:
        await self.activate(4)
        self.assertEqual(self.view.get_regions(RegionKey.LINKED_EDITING), [sublime.Region(1, 4), sublime.Region(7, 10)])
        # Empty ranges stay visible after deleting the whole tag name.
        self.view.run_command("lsp_selection_set", {"regions": [(1, 4)]})
        self.view.run_command("left_delete")
        await self.wait_for_text("<></>")
        self.assertEqual(self.view.get_regions(RegionKey.LINKED_EDITING), [sublime.Region(1, 1), sublime.Region(4, 4)])

    async def test_ranges_are_not_drawn_without_highlight_style(self) -> None:
        userprefs().linked_editing_highlight_style = ""
        self.addCleanup(setattr, userprefs(), 'linked_editing_highlight_style', "underline")
        await self.activate(4)
        self.assertEqual(self.view.get_regions(RegionKey.LINKED_EDITING), [])
        self.insert_characters("x")
        await self.wait_for_text("<divx></divx>")
        self.assertEqual(self.view.get_regions(RegionKey.LINKED_EDITING), [])

    async def test_insert_at_start_of_opening_tag(self) -> None:
        await self.activate(1)
        self.insert_characters("x")
        await self.wait_for_text("<xdiv></xdiv>")

    async def test_edit_in_closing_tag(self) -> None:
        await self.activate(10)
        self.view.run_command("left_delete")
        await self.wait_for_text("<di></di>")
        self.insert_characters("v")
        await self.wait_for_text("<div></div>")
        self.assertEqual(list(self.view.sel()), [sublime.Region(10, 10)])

    async def test_replace_whole_tag(self) -> None:
        await self.activate(4)
        self.view.run_command("lsp_selection_set", {"regions": [(1, 4)]})
        self.insert_characters("span")
        await self.wait_for_text("<span></span>")

    async def test_undo_reverts_all_ranges(self) -> None:
        await self.activate(4)
        self.insert_characters("x")
        await self.wait_for_text("<divx></divx>")
        self.undo()
        await self.wait_for_text(TAGS)

    async def test_undo_restores_caret_after_moving_within_range(self) -> None:
        await self.activate(1)
        self.set_cursor(4)
        # Wait until the caret movement is handled, which happens long before the next keystroke when typing.
        await self.wait_until(lambda: self.linked_editing._selection == [sublime.Region(4, 4)])
        self.insert_characters("x")
        await self.wait_for_text("<divx></divx>")
        self.undo()
        await self.wait_for_text(TAGS)
        self.assertEqual(list(self.view.sel()), [sublime.Region(4, 4)])

    async def test_typed_word_is_undone_at_once(self) -> None:
        await self.activate(4)
        for character in "span":
            self.insert_characters(character)
        await self.wait_for_text("<divspan></divspan>")
        self.undo()
        await self.wait_for_text(TAGS)
        self.assertEqual(list(self.view.sel()), [sublime.Region(4, 4)])

    async def test_edits_are_undone_at_once_after_linked_editing_stops(self) -> None:
        await self.activate(4)
        self.insert_characters("x")
        self.insert_characters("y")
        await self.wait_for_text("<divxy></divxy>")
        self.set_cursor(0)
        await self.wait_until(lambda: not self.linked_editing.is_active())
        self.view.run_command("undo")
        await self.wait_for_text(TAGS)

    async def test_word_pattern_mismatch_stops_linked_editing(self) -> None:
        await self.activate(4)
        self.insert_characters(" ")
        await self.wait_until(lambda: not self.linked_editing.is_active())
        self.assertEqual(self.text(), "<div ></div>")

    async def test_custom_word_pattern(self) -> None:
        await self.activate(4, {'ranges': TAG_RANGES['ranges'], 'wordPattern': '[a-z]*'})
        self.insert_characters("1")
        await self.wait_until(lambda: not self.linked_editing.is_active())
        self.assertEqual(self.text(), "<div1></div>")

    async def test_edit_outside_of_ranges_shifts_ranges(self) -> None:
        await self.activate(4)
        # Insert text in front of the ranges without moving the cursor out of the ranges.
        self.view.run_command("lsp_apply_linked_edits", {"regions": [(0, 0)], "text": "abc"})
        await tick()
        self.assertEqual(self.text(), "abc<div></div>")
        self.assertEqual(self.linked_editing.ranges, (sublime.Region(4, 7), sublime.Region(10, 13)))

    async def test_null_response(self) -> None:
        await self.activate(4, None, expect_active=False)
        await tick()
        self.assertFalse(self.linked_editing.is_active())

    async def test_response_with_different_content_is_ignored(self) -> None:
        await self.activate(4, {'ranges': [make_range(1, 4), make_range(6, 9)]}, expect_active=False)
        await tick()
        self.assertFalse(self.linked_editing.is_active())

    async def test_caret_outside_of_ranges_stops_linked_editing(self) -> None:
        await self.activate(4)
        self.view.run_command("append", {"characters": "\nabc"})
        self.view.run_command("lsp_selection_add", {"regions": [(15, 15)]})
        self.insert_characters("x")
        await self.wait_until(lambda: not self.linked_editing.is_active())
        self.assertEqual(self.text(), "<divx></div>\nabcx")
        self.assertEqual(self.view.get_regions(RegionKey.LINKED_EDITING), [])

    async def test_moving_cursor_out_of_ranges_stops_linked_editing(self) -> None:
        await self.activate(4)
        self.set_cursor(0)
        await self.wait_until(lambda: not self.linked_editing.is_active())
        self.assertEqual(self.view.get_regions(RegionKey.LINKED_EDITING), [])


class LinkedEditingOnSelectionChangeTestCase(LinkedEditingTestCaseBase):

    @override
    async def setUp(self) -> None:
        await super().setUp()
        userprefs().linked_editing = True
        self.addCleanup(setattr, userprefs(), 'linked_editing', False)

    async def insert_tags(self) -> None:
        self.insert_characters(TAGS)
        await self.await_message("textDocument/didChange")

    async def test_request_on_selection_change(self) -> None:
        await self.insert_tags()
        await self.mock_response("textDocument/linkedEditingRange", TAG_RANGES)
        self.set_cursor(4)
        await self.wait_until(self.get_linked_editing().is_active)
        await self.await_message("textDocument/linkedEditingRange")
        self.insert_characters("x")
        await self.wait_for_text("<divx></divx>")

    async def test_caret_movement_during_request_is_handled_when_it_completes(self) -> None:
        await self.insert_tags()
        listener = self.ensure_document_listener_created()
        assert listener
        await self.mock_responses([
            ("textDocument/linkedEditingRange", None),
            ("textDocument/linkedEditingRange", TAG_RANGES),
        ])
        # Only the first request is sent right away. The others are replaced by one request at the latest position.
        for point in (0, 2, 4):
            self.set_cursor(point)
            listener.do_linked_editing_ranges_async()
        params = await self.await_message("textDocument/linkedEditingRange")
        self.assertEqual(params["position"], {"line": 0, "character": 0})
        params = await self.await_message("textDocument/linkedEditingRange")
        self.assertEqual(params["position"], {"line": 0, "character": 4})
        await self.wait_until(listener.linked_editing.is_active)
        self.insert_characters("x")
        await self.wait_for_text("<divx></divx>")

    async def test_request_after_undo(self) -> None:
        await self.insert_tags()
        await self.mock_response("textDocument/linkedEditingRange", TAG_RANGES)
        self.set_cursor(4)
        linked_editing = self.get_linked_editing()
        await self.wait_until(linked_editing.is_active)
        await self.await_message("textDocument/linkedEditingRange")
        self.insert_characters("x")
        await self.wait_for_text("<divx></divx>")
        await self.mock_response("textDocument/linkedEditingRange", TAG_RANGES)
        self.undo()
        await self.wait_for_text(TAGS)
        params = await self.await_message("textDocument/linkedEditingRange")
        self.assertEqual(params["position"], {"line": 0, "character": 4})
        await self.wait_until(linked_editing.is_active)
        self.insert_characters("z")
        await self.wait_for_text("<divz></divz>")

    async def test_only_the_focused_clone_does_linked_editing(self) -> None:
        await self.insert_tags()
        await self.mock_response("textDocument/linkedEditingRange", TAG_RANGES)
        self.set_cursor(4)
        listener = self.ensure_document_listener_created()
        assert listener
        linked_editing = listener.linked_editing
        await self.wait_until(linked_editing.is_active)
        await self.await_message("textDocument/linkedEditingRange")
        # The clone may request ranges too, depending on when the session attaches to it. The other response is for the
        # original view when it gets focus again.
        await self.mock_responses([("textDocument/linkedEditingRange", TAG_RANGES)] * 2)
        window = self.view.window()
        assert window
        window.run_command("clone_file")
        clone = window.active_view()
        assert clone
        self.assertNotEqual(clone.id(), self.view.id())
        # Mark the clone as scratch before closing it, so that closing it doesn't ask to save the changes.
        self.addCleanup(close_test_view, clone)
        await self.wait_until(lambda: not linked_editing.is_active())
        self.assertEqual(self.view.get_regions(RegionKey.LINKED_EDITING), [])
        window.focus_view(self.view)
        await self.wait_until(linked_editing.is_active)
        self.insert_characters("x")
        await self.wait_for_text("<divx></divx>")

    async def test_undo_keeps_caret_position(self) -> None:
        await self.insert_tags()
        await self.mock_response("textDocument/linkedEditingRange", TAG_RANGES)
        self.set_cursor(4)
        linked_editing = self.get_linked_editing()
        await self.wait_until(linked_editing.is_active)
        await self.await_message("textDocument/linkedEditingRange")
        self.insert_characters("x")
        self.insert_characters("y")
        await self.wait_for_text("<divxy></divxy>")
        await self.mock_response("textDocument/linkedEditingRange", TAG_RANGES)
        self.undo()
        await self.wait_for_text(TAGS)
        await self.await_message("textDocument/linkedEditingRange")
        await self.wait_until(linked_editing.is_active)
        self.assertEqual(list(self.view.sel()), [sublime.Region(4, 4)])

    async def test_request_after_deleting_space_typed_after_tag_name(self) -> None:
        await self.insert_tags()
        await self.mock_response("textDocument/linkedEditingRange", TAG_RANGES)
        self.set_cursor(4)
        linked_editing = self.get_linked_editing()
        await self.wait_until(linked_editing.is_active)
        await self.await_message("textDocument/linkedEditingRange")
        self.insert_characters(" ")
        await self.wait_for_text("<div ></div>")
        await self.wait_until(lambda: not linked_editing.is_active())
        await self.mock_response("textDocument/linkedEditingRange", TAG_RANGES)
        self.left_delete()
        await self.wait_for_text(TAGS)
        params = await self.await_message("textDocument/linkedEditingRange")
        self.assertEqual(params["position"], {"line": 0, "character": 4})
        await self.wait_until(linked_editing.is_active)
        self.left_delete()
        await self.wait_for_text("<di></di>")


class LinkedEditingDynamicRegistrationTestCaseBase(TextDocumentTestCase):
    """Each subclass gets its own session, so the capability registered by one test doesn't leak into another."""

    @override
    async def setUp(self) -> None:
        await super().setUp()
        userprefs().linked_editing = True
        self.addCleanup(setattr, userprefs(), 'linked_editing', False)

    async def register_and_activate(self) -> LinkedEditing:
        self.insert_characters(TAGS)
        await self.await_message("textDocument/didChange")
        self.view.run_command("lsp_selection_set", {"regions": [(4, 4)]})
        await self.mock_response("textDocument/linkedEditingRange", TAG_RANGES)
        await self.make_server_do_fake_request("client/registerCapability", {
            "registrations": [{"id": "linked-editing", "method": "textDocument/linkedEditingRange"}]
        })
        await self.await_message("textDocument/linkedEditingRange")
        listener = self.ensure_document_listener_created()
        assert listener
        await self.wait_until(listener.linked_editing.is_active)
        return listener.linked_editing


class LinkedEditingDynamicRegistrationTestCase(LinkedEditingDynamicRegistrationTestCaseBase):

    async def test_request_when_capability_is_registered(self) -> None:
        await self.register_and_activate()
        self.insert_characters("x")
        await self.wait_until(lambda: self.view.substr(sublime.Region(0, self.view.size())) == "<divx></divx>")


class LinkedEditingDynamicUnregistrationTestCase(LinkedEditingDynamicRegistrationTestCaseBase):

    async def test_unregistering_capability_stops_linked_editing(self) -> None:
        linked_editing = await self.register_and_activate()
        await self.make_server_do_fake_request("client/unregisterCapability", {
            "unregisterations": [{"id": "linked-editing", "method": "textDocument/linkedEditingRange"}]
        })
        await self.wait_until(lambda: not linked_editing.is_active())
        self.assertEqual(self.view.get_regions(RegionKey.LINKED_EDITING), [])

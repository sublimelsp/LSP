from test_mocks import MockWindow
from LSP.plugin.core.workspace import ProjectFolders
from LSP.plugin.core.protocol import WorkspaceFolder
import os
from unittest import mock
import unittest
import tempfile


class SortedWorkspaceFoldersTest(unittest.TestCase):

    def test_get_workspace_from_multi_folder_project(self) -> None:
        first = os.path.dirname(__file__)
        with tempfile.TemporaryDirectory() as second:
            folders = ProjectFolders(MockWindow())
            folders.folders = [second, first]
            workspaces, designated = folders.all_and_designated(__file__)
            self.assertListEqual(workspaces, [WorkspaceFolder.from_path(f) for f in (second, first)])
            self.assertEqual(designated.path, first)

    def test_nested_folders(self) -> None:
        with tempfile.TemporaryDirectory() as first:
            second = os.path.join(first, "foobar")
            os.makedirs(second, exist_ok=True)
            with tempfile.TemporaryDirectory() as third:
                folders = ProjectFolders(MockWindow())
                folders.folders = [first, second, third]  # [/tmp/asdf, /tmp/asdf/foobar, /tmp/qwerty]
                file_path = os.path.join(second, "somefile.txt")
                workspaces, designated = folders.all_and_designated(file_path)
                self.assertListEqual(workspaces, [WorkspaceFolder.from_path(f) for f in (first, second, third)])
                self.assertEqual(designated.path, second)


class WorkspaceFolderTest(unittest.TestCase):

    def test_workspace_str(self) -> None:
        workspace = WorkspaceFolder("LSP", "/foo/bar/baz")
        self.assertEqual(str(workspace), "/foo/bar/baz")

    def test_workspace_repr(self) -> None:
        workspace = WorkspaceFolder("LSP", "/foo/bar/baz")
        # This also tests the equality operator
        self.assertEqual(workspace, eval(repr(workspace)))

    def test_workspace_to_dict(self) -> None:
        workspace = WorkspaceFolder("LSP", "/foo/bar/baz")
        lsp_dict = workspace.to_lsp()
        self.assertEqual(lsp_dict, {"name": "LSP", "uri": "file:///foo/bar/baz"})


class WorkspaceFoldersTest(unittest.TestCase):

    def test_load_project_from_empty(self) -> None:
        on_changed = mock.Mock()
        on_switched = mock.Mock()
        window = MockWindow(folders=[])

        wf = ProjectFolders(window)
        wf.on_changed = on_changed
        wf.on_switched = on_switched
        window.set_folders([os.path.dirname(__file__)])
        wf.update()
        assert on_changed.call_count == 1
        on_switched.assert_not_called()

    def test_add_folder(self) -> None:
        on_changed = mock.Mock()
        on_switched = mock.Mock()
        folder = os.path.dirname(__file__)
        parent_folder = os.path.dirname(folder)
        window = MockWindow(folders=[folder])

        wf = ProjectFolders(window)
        wf.on_changed = on_changed
        wf.on_switched = on_switched

        window.set_folders([folder, parent_folder])
        wf.update()
        assert on_changed.call_count == 1
        on_switched.assert_not_called()

    def test_change_folder_order(self) -> None:
        on_changed = mock.Mock()
        on_switched = mock.Mock()
        folder = os.path.dirname(__file__)
        parent_folder = os.path.dirname(folder)
        window = MockWindow(folders=[folder, parent_folder])

        wf = ProjectFolders(window)
        wf.on_changed = on_changed
        wf.on_switched = on_switched

        window.set_folders([parent_folder, folder])
        wf.update()
        on_changed.assert_not_called()
        on_switched.assert_not_called()

    def test_switch_project(self) -> None:
        on_changed = mock.Mock()
        on_switched = mock.Mock()
        folder = os.path.dirname(__file__)
        parent_folder = os.path.dirname(folder)
        window = MockWindow(folders=[folder])

        wf = ProjectFolders(window)
        wf.on_changed = on_changed
        wf.on_switched = on_switched

        window.set_folders([parent_folder])
        wf.update()
        on_changed.assert_not_called()
        assert on_switched.call_count == 1

    def test_open_files_without_project(self) -> None:
        on_changed = mock.Mock()
        on_switched = mock.Mock()

        window = MockWindow(folders=[])

        wf = ProjectFolders(window)
        wf.on_changed = on_changed
        wf.on_switched = on_switched

        wf.update()

        assert on_changed.call_count == 0
        assert on_switched.call_count == 0

        self.assertEqual(wf.folders, [])

    def test_is_foreign(self) -> None:
        on_changed = mock.Mock()
        on_switched = mock.Mock()
        window = MockWindow(folders=["/etc", "/var"])
        wf = ProjectFolders(window)
        wf.on_changed = on_changed
        wf.on_switched = on_switched
        wf.update()
        self.assertTrue(wf.is_foreign("/bin/ls"))
        self.assertTrue(wf.is_inside("/etc/profile"))

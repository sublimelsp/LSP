from test_mocks import MockWindow
from LSP.plugin.core.workspace import ProjectFolders, sorted_workspace_folders
from LSP.plugin.core.protocol import WorkspaceFolder
import os
from unittest import mock
import unittest
import tempfile


class SortedWorkspaceFoldersTest(unittest.TestCase):

    def test_get_workspace_from_multi_folder_project(self) -> None:
        first_project_path = os.path.dirname(__file__)
        second_project_path = tempfile.gettempdir()
        folders = sorted_workspace_folders([second_project_path, first_project_path], __file__)
        first_folder = WorkspaceFolder.from_path(first_project_path)
        second_folder = WorkspaceFolder.from_path(second_project_path)
        self.assertEqual(folders[0], first_folder)
        self.assertEqual(folders[1], second_folder)


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

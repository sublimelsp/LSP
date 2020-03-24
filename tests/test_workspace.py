from test_mocks import MockWindow
from LSP.plugin.core.workspace import ProjectFolders, sorted_workspace_paths, is_subpath_of
from LSP.plugin.core.protocol import WorkspaceFolder
import os
from unittest import mock
import unittest
import tempfile


class SortedWorkspaceFoldersTest(unittest.TestCase):

    def test_get_workspace_from_multi_folder_project(self) -> None:
        nearest_project_path = os.path.dirname(__file__)
        unrelated_project_path = tempfile.gettempdir()
        parent_project_path = os.path.abspath(os.path.join(nearest_project_path, '..'))
        paths = sorted_workspace_paths([unrelated_project_path, parent_project_path, nearest_project_path],
                                           __file__)
        self.assertEqual(paths[0], nearest_project_path)
        self.assertEqual(paths[1], parent_project_path)
        self.assertEqual(paths[2], unrelated_project_path)

    def test_longest_prefix(self) -> None:
        paths = sorted_workspace_paths(["/longer-path", "/short-path"], "/short-path/file.js")
        self.assertEqual(paths[0], "/short-path")


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


class IsSubpathOfTest(unittest.TestCase):

    def is_subpath_case_differs(self) -> None:
        self.assertTrue(is_subpath_of(r"e:\WWW\nthu-ee-iframe\public\include\list_faculty_functions.php",
                                      r"E:\WWW\nthu-ee-iframe"))


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

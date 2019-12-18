from .test_mocks import MockWindow
from .workspace import get_workspace_folders, ProjectFolders
from .protocol import WorkspaceFolder
import os
from unittest import mock
import unittest
import tempfile


class GetWorkspaceFoldersTest(unittest.TestCase):

    def test_get_workspace_from_single_folder_project(self) -> None:
        project_folder = os.path.dirname(__file__)
        folders = get_workspace_folders(MockWindow(folders=[project_folder]), __file__)
        self.assertEqual(folders[0], project_folder)

    def test_get_workspace_from_multi_folder_project(self) -> None:
        first_project_path = os.path.dirname(__file__)
        second_project_path = tempfile.gettempdir()
        folders = get_workspace_folders(MockWindow(folders=[second_project_path, first_project_path]), __file__)
        # first_folder = WorkspaceFolder.from_path(first_project_path)
        # second_folder = WorkspaceFolder.from_path(second_project_path)
        self.assertEqual(folders[0], first_project_path)
        self.assertEqual(folders[1], second_project_path)

    def test_get_workspace_without_folders(self) -> None:
        folders = get_workspace_folders(MockWindow(), __file__)
        self.assertEqual(folders, [])


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

        wf = ProjectFolders(window, on_changed, on_switched)
        window.set_folders([os.path.dirname(__file__)])
        wf.update(__file__)
        assert on_changed.call_count == 1
        on_switched.assert_not_called()

    def test_add_folder(self) -> None:
        on_changed = mock.Mock()
        on_switched = mock.Mock()
        folder = os.path.dirname(__file__)
        parent_folder = os.path.dirname(folder)
        window = MockWindow(folders=[folder])

        wf = ProjectFolders(window, on_changed, on_switched)

        window.set_folders([folder, parent_folder])
        wf.update(__file__)
        assert on_changed.call_count == 1
        on_switched.assert_not_called()

    def test_switch_project(self) -> None:
        on_changed = mock.Mock()
        on_switched = mock.Mock()
        folder = os.path.dirname(__file__)
        parent_folder = os.path.dirname(folder)
        window = MockWindow(folders=[folder])

        wf = ProjectFolders(window, on_changed, on_switched)

        window.set_folders([parent_folder])
        wf.update(__file__)
        on_changed.assert_not_called()
        assert on_switched.call_count == 1

    def test_open_files_without_project(self) -> None:
        on_changed = mock.Mock()
        on_switched = mock.Mock()

        first_file = __file__
        folder = os.path.dirname(__file__)
        parent_folder = os.path.dirname(folder)
        file_in_parent_folder = os.path.join(parent_folder, "test_file.py")

        window = MockWindow(folders=[])

        wf = ProjectFolders(window, on_changed, on_switched)

        wf.update(first_file)

        assert on_changed.call_count == 0
        on_switched.assert_not_called()

        wf.update(file_in_parent_folder)

        assert on_changed.call_count == 0
        assert on_switched.call_count == 0

        self.assertEqual(wf.folders, [])

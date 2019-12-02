from .test_mocks import MockWindow
from .workspace import WorkspaceFolder, get_workspace_folders
from os.path import dirname
from unittest import TestCase
import tempfile


class WorkspaceTest(TestCase):

    def test_get_workspace_from_single_folder_project(self) -> None:
        project_folder = dirname(__file__)
        folders = get_workspace_folders(MockWindow(folders=[project_folder]), __file__)
        folder = WorkspaceFolder.from_path(project_folder)
        self.assertEqual(folders[0], folder)

    def test_get_workspace_from_multi_folder_project(self) -> None:
        first_project_path = dirname(__file__)
        second_project_path = tempfile.gettempdir()
        folders = get_workspace_folders(MockWindow(folders=[second_project_path, first_project_path]), __file__)
        first_folder = WorkspaceFolder.from_path(first_project_path)
        second_folder = WorkspaceFolder.from_path(second_project_path)
        self.assertEqual(folders[0], first_folder)
        self.assertEqual(folders[1], second_folder)

    def test_get_workspace_without_folders(self) -> None:
        project_folder = dirname(__file__)
        folders = get_workspace_folders(MockWindow(), __file__)
        folder = WorkspaceFolder.from_path(project_folder)
        self.assertEqual(folders[0], folder)

    def test_workspace_str(self) -> None:
        workspace = WorkspaceFolder("LSP", "/foo/bar/baz")
        self.assertEqual(str(workspace), "/foo/bar/baz")

    def test_workspace_repr(self) -> None:
        workspace = WorkspaceFolder("LSP", "/foo/bar/baz")
        # This also tests the equality operator
        self.assertEqual(workspace, eval(repr(workspace)))

    def test_workspace_to_dict(self) -> None:
        workspace = WorkspaceFolder("LSP", "/foo/bar/baz")
        lsp_dict = workspace.to_dict()
        self.assertEqual(lsp_dict, {"name": "LSP", "uri": "file:///foo/bar/baz"})

from __future__ import annotations

from LSP.plugin.core.workspace import is_subpath_of
from LSP.plugin.core.workspace import sorted_workspace_folders
from LSP.plugin.core.workspace import WorkspaceFolder
from pathlib import Path
import os
import tempfile
import unittest


class SortedWorkspaceFoldersTest(unittest.TestCase):

    def test_get_workspace_from_multi_folder_project(self) -> None:
        nearest_project_path = os.path.dirname(__file__)
        unrelated_project_path = tempfile.gettempdir()
        parent_project_path = os.path.abspath(os.path.join(nearest_project_path, '..'))
        folders = sorted_workspace_folders([unrelated_project_path, parent_project_path, nearest_project_path],
                                           __file__)
        nearest_folder = WorkspaceFolder.from_path(nearest_project_path)
        parent_folder = WorkspaceFolder.from_path(parent_project_path)
        unrelated_folder = WorkspaceFolder.from_path(unrelated_project_path)
        self.assertEqual(folders[0], nearest_folder)
        self.assertEqual(folders[1], parent_folder)
        self.assertEqual(folders[2], unrelated_folder)

    def test_longest_prefix(self) -> None:
        with tempfile.TemporaryDirectory() as root:
            longer_path = Path(root, "longer-path")
            short_path = Path(root, "short-path")
            longer_path.mkdir()
            short_path.mkdir()
            folders = sorted_workspace_folders([str(longer_path), str(short_path)], str(short_path / "file.js"))
            self.assertEqual(folders[0].path, str(short_path))

    def test_skips_missing_folders(self) -> None:
        existing_path = Path(__file__).parent
        missing_path = existing_path / "this-folder-does-not-exist"
        folders = sorted_workspace_folders([str(missing_path), str(existing_path)], str(missing_path / "file.js"))
        self.assertEqual(folders, [WorkspaceFolder.from_path(str(existing_path))])

    def test_all_folders_missing(self) -> None:
        missing_path = Path(__file__).parent / "this-folder-does-not-exist"
        self.assertEqual(sorted_workspace_folders([str(missing_path)], str(missing_path / "file.js")), [])


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

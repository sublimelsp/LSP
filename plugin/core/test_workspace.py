from .test_mocks import MockView
from .test_mocks import MockWindow
from .workspace import maybe_get_first_workspace_from_window
from .workspace import maybe_get_workspace_from_view
from .workspace import WorkspaceFolder
from os.path import dirname
from unittest import TestCase


class WorkspaceTest(TestCase):

    def test_get_first_workspace_from_window_single_file(self) -> None:
        workspace = maybe_get_first_workspace_from_window(MockWindow())
        self.assertIsNone(workspace)

        workspace = maybe_get_first_workspace_from_window(MockWindow(folders=[dirname(__file__)]))
        self.assertIsNotNone(workspace)
        assert workspace  # for mypy
        self.assertEqual(workspace.path, dirname(__file__))
        self.assertEqual(workspace.name, "core")

    def test_get_workspace_from_view(self) -> None:
        view = MockView(__file__)
        window = MockWindow(files_in_groups=[[view]])
        workspace = maybe_get_workspace_from_view(view)
        self.assertIsNotNone(workspace)
        assert workspace  # for mypy
        self.assertEqual(workspace.path, dirname(__file__))
        self.assertEqual(workspace.name, "core")

        workspace = maybe_get_workspace_from_view(window)
        self.assertIsNotNone(workspace)
        assert workspace  # for mypy
        self.assertEqual(workspace.path, dirname(__file__))
        self.assertEqual(workspace.name, "core")

        view._file_name = None
        workspace = maybe_get_workspace_from_view(view)
        self.assertIsNone(workspace)

        workspace = maybe_get_workspace_from_view(window)
        self.assertIsNone(workspace)

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

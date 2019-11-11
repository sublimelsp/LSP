from .test_mocks import MockWindow
from .url import filename_to_uri
from .workspace import get_common_prefix_of_workspaces_for_window
from .workspace import get_workspaces_from_window
from .workspace import Workspace
from os.path import basename
from os.path import dirname
from os.path import join
from os.path import realpath
from unittest import TestCase
import sys


BASE_DIR = realpath(join(dirname(__file__), "..", ".."))
# Cannot use "from .settings import PLUGIN_NAME" because it imports the sublime module
PLUGIN_NAME = 'LSP'


class WorkspaceTest(TestCase):

    def test_sanity_check(self) -> None:
        self.assertEqual(basename(BASE_DIR), PLUGIN_NAME)

    def test_get_common_prefix_of_workspaces_for_window(self) -> None:
        window = MockWindow()
        window._project_file_name = join(BASE_DIR, "foo.sublime-project")
        window._project_data = {
            "folders": [
                {"path": join(BASE_DIR, "Commands")},
                {"path": join(BASE_DIR, "docs")},
                {"path": join(BASE_DIR, "icons")},
            ]
        }
        prefix = get_common_prefix_of_workspaces_for_window(window)
        self.assertIsNotNone(prefix)
        assert prefix  # Let mypy know that this is not None.
        self.assertEqual(realpath(prefix), realpath(BASE_DIR))

    def test_get_workspaces_from_window_single_file(self) -> None:
        window = MockWindow()
        window._project_file_name = ""
        window._project_data = None
        workspaces = get_workspaces_from_window(window)
        self.assertIsNone(workspaces)

    def test_get_workspaces_from_window_single_window(self) -> None:
        window = MockWindow()
        window._project_file_name = ""
        window._project_data = {"folders": [{"path": BASE_DIR}]}
        workspaces = get_workspaces_from_window(window)
        self.assertIsNotNone(workspaces)
        assert workspaces  # Help mypy deduce that this variable is not None.
        workspaces = list(workspaces)
        self.assertEqual(len(workspaces), 1)
        self.assertEqual(workspaces[0].name, "LSP")
        self.assertEqual(workspaces[0].uri, filename_to_uri(BASE_DIR))

    def get_absolute_sample_path(self) -> str:
        # This is /opt/sublime_text on Linux and I presume the Sublime Text
        # installation path in general.
        return sys.path[0]

    def test_get_workspaces_from_window_project_file(self) -> None:
        window = MockWindow()
        window._project_file_name = join(BASE_DIR, "foo.sublime-project")
        window._project_data = {
            "folders": [
                {"name": "first", "path": "docs"},
                {"name": "second", "path": self.get_absolute_sample_path()},
                {"name": "third", "path": "plugin/core/../core"},
                {"path": "Menus"}
            ]
        }
        workspaces = get_workspaces_from_window(window)
        self.assertIsNotNone(workspaces)
        assert workspaces  # Help mypy deduce that this variable is not None.
        workspaces = list(workspaces)
        self.assertEqual(len(workspaces), 4)
        self.assertEqual(workspaces[0].name, "first")
        self.assertEqual(workspaces[0].uri, filename_to_uri(join(BASE_DIR, "docs")))
        self.assertEqual(workspaces[1].name, "second")
        self.assertEqual(workspaces[1].uri, filename_to_uri(self.get_absolute_sample_path()))
        self.assertEqual(workspaces[2].name, "third")
        self.assertEqual(workspaces[2].uri, filename_to_uri(join(BASE_DIR, "plugin", "core")))
        self.assertEqual(workspaces[3].name, "Menus")
        self.assertEqual(workspaces[3].uri, filename_to_uri(join(BASE_DIR, "Menus")))

    def test_workspace_str(self) -> None:
        workspace = Workspace("LSP", "file:///foo/bar/baz")
        # This also tests the equality operator
        self.assertEqual(str(workspace), "file:///foo/bar/baz")

    def test_workspace_repr(self) -> None:
        workspace = Workspace("LSP", "file:///foo/bar/baz")
        # This also tests the equality operator
        self.assertEqual(workspace, eval(repr(workspace)))

    def test_workspace_to_dict(self) -> None:
        workspace = Workspace("LSP", "file:///foo/bar/baz")
        lsp_dict = workspace.to_dict()
        self.assertEqual(lsp_dict, {"name": "LSP", "uri": "file:///foo/bar/baz"})

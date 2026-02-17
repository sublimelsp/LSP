from __future__ import annotations

from ...protocol import WorkspaceFolder as LspWorkspaceFolder
from .types import diff
from .types import matches_pattern
from .types import sublime_pattern_to_glob
from .url import filename_to_uri
from typing import Any
import os
import sublime


def is_subpath_of(file_path: str, potential_subpath: str) -> bool:
    try:
        file_path = os.path.abspath(file_path)
        potential_subpath = os.path.abspath(potential_subpath)
        return not os.path.relpath(file_path, potential_subpath).startswith("..")
    except ValueError:
        return False


class WorkspaceFolder:

    __slots__ = ('name', 'path')

    def __init__(self, name: str, path: str) -> None:
        self.name = name
        self.path = path

    @classmethod
    def from_path(cls, path: str) -> WorkspaceFolder:
        return cls(os.path.basename(path) or path, path)

    def __hash__(self) -> int:
        return hash((self.name, self.path))

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}('{self.name}', '{self.path}')"

    def __str__(self) -> str:
        return self.path

    def __eq__(self, other: Any) -> bool:
        if isinstance(other, WorkspaceFolder):
            return self.name == other.name and self.path == other.path
        return False

    def to_lsp(self) -> LspWorkspaceFolder:
        return {"name": self.name, "uri": self.uri()}

    def uri(self) -> str:
        return filename_to_uri(self.path)

    def includes_uri(self, uri: str) -> bool:
        return uri.startswith(self.uri())


class ProjectFolders:

    def __init__(self, window: sublime.Window) -> None:
        self._window = window
        self.folders: list[str] = self._window.folders()
        # Per-folder ignore patterns. The list order matches the order of self.folders.
        self._folders_exclude_patterns: list[list[str]] = []
        self._update_exclude_patterns(self.folders)

    def _update_exclude_patterns(self, folders: list[str]) -> None:
        # Ensure that the number of patterns matches the number of folders so that accessing by index never throws.
        self._folders_exclude_patterns = [[]] * len(folders)
        project_data = self._window.project_data()
        if not isinstance(project_data, dict):
            return
        for i, folder in enumerate(project_data.get('folders', [])):
            exclude_patterns = []
            # Use canoncial path from `window.folders` rather than potentially relative path from project data.
            path = folders[i]
            for pattern in folder.get('folder_exclude_patterns', []):
                if pattern.startswith('//'):
                    exclude_patterns.append(sublime_pattern_to_glob(pattern, True, path))
                elif pattern.startswith('/'):
                    exclude_patterns.append(sublime_pattern_to_glob(pattern, True))
                else:
                    exclude_patterns.append(sublime_pattern_to_glob('//' + pattern, True, path))
                    exclude_patterns.append(sublime_pattern_to_glob('//**/' + pattern, True, path))
            self._folders_exclude_patterns[i] = exclude_patterns

    def update(self) -> bool:
        new_folders = self._window.folders()
        self._update_exclude_patterns(new_folders)
        added, removed = diff(self.folders, new_folders)
        if added or removed:
            self.folders = new_folders
            return True
        return False

    def includes_path(self, file_path: str) -> bool:
        if self.folders:
            return any(is_subpath_of(file_path, folder) for folder in self.folders)
        return True

    def includes_excluded_path(self, file_path: str) -> bool:
        """Path is excluded if it's within one or more workspace folders and in at least one of the folders it's not
        excluded using `folder_exclude_patterns`."""
        if not self.folders:
            return False
        is_excluded = False
        for i, folder in enumerate(self.folders):
            if not is_subpath_of(file_path, folder):
                continue
            exclude_patterns = self._folders_exclude_patterns[i]
            is_excluded = matches_pattern(file_path, exclude_patterns)
            if not is_excluded:
                break
        return is_excluded

    def contains(self, view_or_file_name: str | sublime.View) -> bool:
        file_path = view_or_file_name.file_name() if isinstance(view_or_file_name, sublime.View) else view_or_file_name
        return self.includes_path(file_path) if file_path else False

    def get_workspace_folders(self) -> list[WorkspaceFolder]:
        return [WorkspaceFolder.from_path(f) for f in self.folders]


def sorted_workspace_folders(folders: list[str], file_path: str) -> list[WorkspaceFolder]:
    matching_paths: list[str] = []
    other_paths: list[str] = []

    for folder in folders:
        if is_subpath_of(file_path, folder):
            if matching_paths and len(folder) > len(matching_paths[0]):
                matching_paths.insert(0, folder)
            else:
                matching_paths.append(folder)
        else:
            other_paths.append(folder)

    return [WorkspaceFolder.from_path(path) for path in matching_paths + other_paths]


def enable_in_project(window: sublime.Window, config_name: str) -> None:
    project_data = window.project_data()
    if isinstance(project_data, dict):
        project_settings = project_data.setdefault('settings', dict())
        project_lsp_settings = project_settings.setdefault('LSP', dict())
        project_client_settings = project_lsp_settings.setdefault(config_name, dict())
        project_client_settings['enabled'] = True
        window.set_project_data(project_data)
    else:
        sublime.message_dialog(
            f"Can't enable {config_name} in the current workspace. Ensure that the project is saved first.")


def disable_in_project(window: sublime.Window, config_name: str) -> None:
    project_data = window.project_data()
    if isinstance(project_data, dict):
        project_settings = project_data.setdefault('settings', dict())
        project_lsp_settings = project_settings.setdefault('LSP', dict())
        project_client_settings = project_lsp_settings.setdefault(config_name, dict())
        project_client_settings['enabled'] = False
        window.set_project_data(project_data)
    else:
        sublime.message_dialog(
            f"Can't disable {config_name} in the current workspace. Ensure that the project is saved first.")

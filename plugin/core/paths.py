from __future__ import annotations

from ...protocol import DocumentUri
from .sessions import Session
from .views import parse_uri
from pathlib import Path
from typing import Iterable


def simple_path(session: Session | None, uri: DocumentUri) -> str:
    scheme, path = parse_uri(uri)
    if not session or scheme != 'file':
        return path
    simple_path = simple_project_path([Path(folder.path) for folder in session.get_workspace_folders()], Path(path))
    return str(simple_path) if simple_path else path


def project_path(project_folders: Iterable[Path], file_path: Path) -> Path | None:
    """
    The project path of `/path/to/project/file` in the project `/path/to/project` is `file`.
    """
    folder_path = split_project_path(project_folders, file_path)
    if folder_path is None:
        return None
    _, file = folder_path
    return file


def simple_project_path(project_folders: Iterable[Path], file_path: Path) -> Path | None:
    """
    The simple project path of `/path/to/project/file` in the project `/path/to/project` is `project/file`.
    """
    folder_path = split_project_path(project_folders, file_path)
    if folder_path is None:
        return None
    folder, file = folder_path
    return folder.name / file


def resolve_simple_project_path(project_folders: Iterable[Path], file_path: Path) -> Path | None:
    """
    The inverse of `simple_project_path()`.
    """
    parts = file_path.parts
    folder_name = parts[0]
    for folder in project_folders:
        if folder.name == folder_name:
            return folder / Path(*parts[1:])
    return None


def project_base_dir(project_folders: Iterable[Path], file_path: Path) -> Path | None:
    """
    The project base dir of `/path/to/project/file` in the project `/path/to/project` is `/path/to`.
    """
    folder_path = split_project_path(project_folders, file_path)
    if folder_path is None:
        return None
    folder, _ = folder_path
    return folder.parent


def split_project_path(project_folders: Iterable[Path], file_path: Path) -> tuple[Path, Path] | None:
    abs_path = file_path.resolve()
    for folder in project_folders:
        try:
            rel_path = abs_path.relative_to(folder)
        except ValueError:
            continue
        return folder, rel_path
    return None

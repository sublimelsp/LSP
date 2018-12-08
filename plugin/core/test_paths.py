import unittest
import random
import string
from .test_windows import MockWindow, MockView
from .workspace import get_project_path

try:
    from typing import List, Optional, Any, Iterable
    assert List and Optional and Any and Iterable
except ImportError:
    pass


def random_file_string():
    return ''.join(
        random.choice(
            string.ascii_lowercase + string.digits + string.whitespace + "."
        )
        for _ in range(random.randint(3, 24))
    )


def mock_file_group(root_dir: str, file_count: int):
    out = []
    for i in range(file_count):
        out.append(MockView(root_dir + "/" + random_file_string()))
        if random.random() > 0.9:
            subcontents = mock_file_group(
                root_dir + "/" + random_file_string(),
                random.randint(1, file_count)
            )
            random.shuffle(subcontents)
            out.extend(subcontents)
    return out


class GetProjectPathTests(unittest.TestCase):

    def test_unrelated_files_1(self):
        window = MockWindow([
            [
                MockView("/etc/some_configuration_file"),
            ],
            mock_file_group("/home/user/project_a", 10),
            mock_file_group("/home/user_project_b", 10)
        ])

        window.set_folders(["/home/user/project_a", "/home/user/project_b"])
        self.assertEqual(get_project_path(window), None)

    def test_unrelated_files_2(self):
        window = MockWindow([
            mock_file_group("/home/user/project_a", 10),
            mock_file_group("/home/user_project_b", 10),
            [
                MockView("/etc/some_configuration_file"),
            ]
        ])

        window.set_folders(["/home/user/project_a", "/home/user/project_b"])
        self.assertEqual(get_project_path(window), "/home/user/project_a")

    def test_single_project(self):
        window = MockWindow([
            mock_file_group("/home/user/project_a", 10)
        ])

        window.set_folders(["/home/user/project_a"])
        self.assertEqual(get_project_path(window), "/home/user/project_a")

    def test_double_project(self):
        window = MockWindow([
            mock_file_group("/home/user/project_a", 10),
            mock_file_group("/home/user/project_b", 10)
        ])

        window.set_folders(["/home/user/project_a", "/home/user/project_b"])
        self.assertEqual(get_project_path(window), "/home/user/project_a")

    def test_triple_project(self):
        window = MockWindow([
            mock_file_group("/home/user/project_a", 10),
            mock_file_group("/home/user/project_b", 10)
        ])

        window.set_folders(["/home/user/project_a", "/home/user/project_b"])
        self.assertEqual(get_project_path(window), "/home/user/project_a")

    def test_no_project(self):
        window = MockWindow([[MockView("/just/pick/the/current/directory.txt")]])
        window.set_folders([])

        self.assertEqual(get_project_path(window), "/just/pick/the/current")

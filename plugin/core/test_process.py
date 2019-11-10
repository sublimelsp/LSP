# from .process import get_server_working_directory_and_ensure_existence
# from os.path import split
from .process import add_extension_if_missing
from .process import start_server
from .test_mocks import MockWindow
from .test_session import test_config
from copy import deepcopy
from unittest import TestCase
import os


class ProcessModuleTest(TestCase):

    def test_add_extension_if_missing(self) -> None:
        if os.name != "nt":
            self.skipTest("only useful for windows")
        # TODO: More extensive tests.
        args = add_extension_if_missing(["cmd"])
        self.assertListEqual(args, ["cmd"])

    # def test_get_server_working_directory_and_ensure_existence(self) -> None:
    #     cwd = get_server_working_directory_and_ensure_existence(test_config)
    #     cwd, leaf = split(cwd)
    #     self.assertEqual(leaf, "test")
    #     cwd, leaf = split(cwd)
    #     self.assertEqual(leaf, "LSP")

    def test_start_server_failure(self) -> None:
        config = deepcopy(test_config)
        config.binary_args = ["some_file_that_most_definitely_does_not_exist", "a", "b", "c"]
        with self.assertRaises(FileNotFoundError):
            start_server(MockWindow(), config, config.binary_args, {}, False)

    def test_start_server(self) -> None:
        config = deepcopy(test_config)  # Don't modify the original dict.
        if os.name == "nt":
            config.binary_args = ["cmd.exe"]
        else:
            config.binary_args = ["ls"]
        config.binary_args.extend(["a", "b", "c"])
        popen = start_server(MockWindow(), config, config.binary_args, {}, False)
        self.assertIsNotNone(popen)
        assert popen
        args = list(map(str, popen.args[1:]))  # type: ignore
        self.assertListEqual(args, ["a", "b", "c"])

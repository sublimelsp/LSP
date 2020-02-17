import unittest
from os import path
import json
from LSP.plugin.core.completion import format_completion, parse_completion_response
try:
    from typing import Optional, Dict
    assert Optional and Dict
except ImportError:
    pass


def load_completion_sample(name: str) -> 'Dict':
    return json.load(open(path.join(path.dirname(__file__), name + ".json")))


pyls_completion_sample = load_completion_sample("pyls_completion_sample")
clangd_completion_sample = load_completion_sample("clangd_completion_sample")
intelephense_completion_sample = load_completion_sample("intelephense_completion_sample")


class CompletionResponseParsingTests(unittest.TestCase):

    def test_no_response(self):
        self.assertEqual(parse_completion_response(None), ([], False))

    def test_array_response(self):
        self.assertEqual(parse_completion_response([]), ([], False))

    def test_dict_response(self):
        self.assertEqual(parse_completion_response({'items': []}), ([], False))

    def test_incomplete_dict_response(self):
        self.assertEqual(parse_completion_response({'items': [], 'isIncomplete': True}), ([], True))


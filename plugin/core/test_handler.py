from .handlers import LanguageHandler
from .test_session import test_config
from .types import ClientConfig

import unittest


class TestHandler(LanguageHandler):
    # on_start = None  # type: Optional[Callable]
    # on_initialized = None  # type: Optional[Callable]

    @property
    def name(self) -> str:
        return "test"

    @property
    def config(self) -> ClientConfig:
        return test_config


class LanguageHandlerTest(unittest.TestCase):
    def test_instantiate(self):
        handlers = LanguageHandler.instantiate_all()
        self.assertEqual(len(handlers), 1)
        first_handler = handlers[0]
        self.assertEqual(first_handler.name, "test")
        self.assertEqual(first_handler.config, test_config)

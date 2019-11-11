from .handlers import LanguageHandler
from .test_mocks import TEST_CONFIG
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
        return TEST_CONFIG


class LanguageHandlerTest(unittest.TestCase):
    def test_instantiate(self):
        handlers = LanguageHandler.instantiate_all()
        self.assertEqual(len(handlers), 1)
        first_handler = handlers[0]
        self.assertEqual(first_handler.name, "test")
        self.assertEqual(first_handler.config, TEST_CONFIG)

from LSP.plugin.core.types import LanguageConfig
from LSP.plugin.core.types import ClientConfig
from unittest import TestCase


class TypesTests(TestCase):

    def test_language_config_score(self) -> None:
        lang = LanguageConfig("php", ["source.php", "embedding.php"])
        self.assertTrue(lang.supports("source.php"))
        self.assertTrue(lang.supports("embedding.php"))
        self.assertFalse(lang.supports("source.js"))
        lang = LanguageConfig("html", ["text.html"])
        self.assertFalse(lang.supports("source.php"))
        self.assertFalse(lang.supports("source.js"))
        self.assertTrue(lang.supports("text.html"))
        lang = LanguageConfig("python", ["source.python"])
        self.assertFalse(lang.supports("source.php"))
        self.assertFalse(lang.supports("source.js"))
        self.assertFalse(lang.supports("text.html"))
        self.assertTrue(lang.supports("source.python"))

    def test_language_config_repr(self) -> None:
        lang = LanguageConfig("ocaml", ["source.ocaml"])
        self.assertEqual(lang, eval(repr(lang)))

    def test_client_config_score(self) -> None:
        config = ClientConfig(
            name="amazing-language-server",
            binary_args=[],
            tcp_port=None,
            languages=[
                LanguageConfig("python", ["source.python"]),
                LanguageConfig("php", ["embedding.php"]),
                LanguageConfig("html", ["text.html"]),
                LanguageConfig("txt", ["text.plain"])])
        self.assertTrue(config.supports("source.python"))
        self.assertTrue(config.supports("embedding.php"))
        self.assertTrue(config.supports("text.html"))
        self.assertTrue(config.supports("text.plain"))
        self.assertFalse(config.supports("source.c"))
        self.assertFalse(config.supports("source.c++"))
        self.assertFalse(config.supports("source.ocaml"))

from setup import TextDocumentTestCase
from LSP.plugin.core.typing import Generator
from LSP.plugin.symbols import symbol_information_to_quick_panel_item
from LSP.plugin.core.protocol import SymbolTag

class QueryCompletionsTests(TextDocumentTestCase):
    def test_show_deprecated_flag_for_symbol_information(self) -> 'Generator':
        symbol_information = {
            "name": 'Name',
            "kind": 6,  # Method
            "tags": [SymbolTag.Deprecated],
        }
        formatted_symbol_information = symbol_information_to_quick_panel_item(symbol_information, show_file_name=False)
        self.assertEqual('⚠ Method - Deprecated', formatted_symbol_information.annotation)

    def test_dont_show_deprecated_flag_for_symbol_information(self) -> 'Generator':
        symbol_information = {
            "name": 'Name',
            "kind": 6,  # Method
            # to deprecated tags
        }
        formatted_symbol_information = symbol_information_to_quick_panel_item(symbol_information, show_file_name=False)
        self.assertEqual('Method', formatted_symbol_information.annotation)

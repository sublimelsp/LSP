from __future__ import annotations

from LSP.plugin.formatting import get_formatter
from typing import Any
from unittest import TestCase
from unittest.mock import MagicMock
from unittest.mock import patch


def mock_window_manager(project_data: Any, formatters: dict[str, str] | None = None) -> MagicMock:
    window_manager = MagicMock()
    window_manager.window.project_data.return_value = project_data
    window_manager.formatters = formatters or {}
    return window_manager


class GetFormatterTests(TestCase):

    def get_formatter(self, window_manager: MagicMock | None, base_scope: str) -> str | None:
        with patch('LSP.plugin.formatting.windows.lookup', return_value=window_manager):
            return get_formatter(MagicMock(), base_scope)

    def test_project_formatter_with_dotted_base_scope(self) -> None:
        project_data = {
            'settings': {
                'LSP': {
                    'formatters': {
                        'source.ts': 'oxfmt',
                        'text.html.vue': 'oxfmt',
                    }
                }
            }
        }
        window_manager = mock_window_manager(project_data)
        self.assertEqual(self.get_formatter(window_manager, 'source.ts'), 'oxfmt')
        self.assertEqual(self.get_formatter(window_manager, 'text.html.vue'), 'oxfmt')
        self.assertIsNone(self.get_formatter(window_manager, 'source.python'))

    def test_project_without_formatters(self) -> None:
        window_manager = mock_window_manager({'settings': {'LSP': {}}})
        self.assertIsNone(self.get_formatter(window_manager, 'source.ts'))

    def test_window_formatter_without_project(self) -> None:
        window_manager = mock_window_manager(None, {'text.html.vue': 'oxfmt'})
        self.assertEqual(self.get_formatter(window_manager, 'text.html.vue'), 'oxfmt')

    def test_no_window_manager(self) -> None:
        self.assertIsNone(self.get_formatter(None, 'source.ts'))

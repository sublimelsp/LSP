from __future__ import annotations

from LSP.plugin.edit import utf16_to_code_points
import unittest


class LspRenamePanelTests(unittest.TestCase):

    def test_utf16_ascii(self):
        s = 'abc'
        self.assertEqual(utf16_to_code_points(s, 0), 0)
        self.assertEqual(utf16_to_code_points(s, 1), 1)
        self.assertEqual(utf16_to_code_points(s, 2), 2)
        self.assertEqual(utf16_to_code_points(s, 3), 3)  # EOL after last character should count as its own code point
        self.assertEqual(utf16_to_code_points(s, 1337), 3)  # clamp to EOL

    def test_utf16_deseret_letter(self):
        # https://microsoft.github.io/language-server-protocol/specifications/specification-current/#textDocuments
        s = 'a𐐀b'
        self.assertEqual(len(s), 3)
        self.assertEqual(utf16_to_code_points(s, 0), 0)
        self.assertEqual(utf16_to_code_points(s, 1), 1)
        self.assertEqual(utf16_to_code_points(s, 2), 1)  # 𐐀 needs 2 UTF-16 code units, so this is still at code point 1
        self.assertEqual(utf16_to_code_points(s, 3), 2)
        self.assertEqual(utf16_to_code_points(s, 4), 3)
        self.assertEqual(utf16_to_code_points(s, 1337), 3)

    def test_utf16_emoji(self):
        s = 'a😀x'
        self.assertEqual(len(s), 3)
        self.assertEqual(utf16_to_code_points(s, 0), 0)
        self.assertEqual(utf16_to_code_points(s, 1), 1)
        self.assertEqual(utf16_to_code_points(s, 2), 1)
        self.assertEqual(utf16_to_code_points(s, 3), 2)
        self.assertEqual(utf16_to_code_points(s, 4), 3)
        self.assertEqual(utf16_to_code_points(s, 1337), 3)

    def test_utf16_emoji_zwj_sequence(self):
        # https://unicode.org/emoji/charts/emoji-zwj-sequences.html
        s = 'a😵‍💫x'
        self.assertEqual(len(s), 5)
        self.assertEqual(s, 'a\U0001f635\u200d\U0001f4abx')
        # 😵‍💫 consists of 5 UTF-16 code units and Python treats it as 3 characters
        self.assertEqual(utf16_to_code_points(s, 0), 0)  # a
        self.assertEqual(utf16_to_code_points(s, 1), 1)  # \U0001f635
        self.assertEqual(utf16_to_code_points(s, 2), 1)  # \U0001f635
        self.assertEqual(utf16_to_code_points(s, 3), 2)  # \u200d (zero width joiner)
        self.assertEqual(utf16_to_code_points(s, 4), 3)  # \U0001f4ab
        self.assertEqual(utf16_to_code_points(s, 5), 3)  # \U0001f4ab
        self.assertEqual(utf16_to_code_points(s, 6), 4)  # x
        self.assertEqual(utf16_to_code_points(s, 7), 5)  # after x
        self.assertEqual(utf16_to_code_points(s, 1337), 5)

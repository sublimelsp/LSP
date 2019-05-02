from .signature_help import create_signature_help, SignatureHelp, get_documentation
from .types import Settings
import unittest

language_id = "asdf"
settings = Settings()
signature = {
    'label': 'foo_bar(value: int) -> None',
    'documentation': {'value': 'The default function for foobaring'},
    'parameters': [{
        'label': 'value',
        'documentation': {
            'value': 'A number to foobar on'
        }
    }]
}  # type: dict
signature_overload = {
    'label': 'foo_bar(value: int, multiplier: int) -> None',
    'documentation': {'value': 'Foobaring with a multipler'},
    'parameters': [{
        'label': 'value',
        'documentation': {
            'value': 'A number to foobar on'
        }
    }, {
        'label': 'multiplier',
        'documentation': 'Change foobar to work on larger increments'
    }]
}  # type: dict


SUBLIME_SINGLE_SIGNATURE = """```asdf
foo_bar(value: int) -> None
```

**value**

* *A number to foobar on*

The default function for foobaring"""

VSCODE_SINGLE_SIGNATURE = """<div class="highlight"><pre>
foo_bar(<span style="font-weight: bold; text-decoration: underline">value</span>: int) -&gt; None
</pre></div>
A number to foobar on
The default function for foobaring"""


class GetDocumentationTests(unittest.TestCase):

    def test_absent(self):
        self.assertIsNone(get_documentation({}))

    def test_is_str(self):
        self.assertEqual(get_documentation({'documentation': 'str'}), 'str')

    def test_is_dict(self):
        self.assertEqual(get_documentation({'documentation': {'value': 'value'}}), 'value')


class CreateSignatureHelpTests(unittest.TestCase):

    def test_none(self):
        self.assertIsNone(create_signature_help(None, language_id, settings))

    def test_empty(self):
        self.assertIsNone(create_signature_help({}, language_id, settings))

    def test_default_indices(self):

        help = create_signature_help({"signatures": [signature]}, language_id, settings)

        self.assertIsNotNone(help)
        if help:
            self.assertEqual(help._active_signature, 0)
            self.assertEqual(help._active_parameter, -1)


class SublimeSignatureHelpTests(unittest.TestCase):

    def test_single_signature(self):
        help = SignatureHelp([signature], language_id)
        self.assertIsNotNone(help)
        if help:
            content = help.build_popup_content()
            self.assertEqual(content, SUBLIME_SINGLE_SIGNATURE)


class VsCodeSignatureHelpTests(unittest.TestCase):

    def test_single_signature(self):
        help = SignatureHelp([signature], language_id, highlight_parameter=True)
        self.assertIsNotNone(help)
        if help:
            content = help.build_popup_content()
            self.assertEqual(content, VSCODE_SINGLE_SIGNATURE)

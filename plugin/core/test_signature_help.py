from .signature_help import create_signature_help, SignatureHelp, get_documentation, replace_active_parameter
from .types import Settings
import unittest

language_id = "python"
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
    'documentation': {'value': 'Foobaring with a multiplier'},
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


SUBLIME_SINGLE_SIGNATURE = """```python
foo_bar(value: int) -> None
```

**value**

* *A number to foobar on*

The default function for foobaring"""

SUBLIME_OVERLOADS_FIRST = """**1** of **2** overloads (use the ↑ ↓ keys to navigate):

```python
foo_bar(value: int) -> None
```

**value**

* *A number to foobar on*

The default function for foobaring"""

SUBLIME_OVERLOADS_SECOND = """**2** of **2** overloads (use the ↑ ↓ keys to navigate):

```python
foo_bar(value: int, multiplier: int) -> None
```

**value**

* *A number to foobar on*

**multiplier**

* *Change foobar to work on larger increments*

Foobaring with a multiplier"""

VSCODE_SINGLE_SIGNATURE = """<div class="highlight"><pre>
foo_bar(<span style="font-weight: bold; text-decoration: underline">value</span>: int) -&gt; None
</pre></div>
A number to foobar on
The default function for foobaring"""

VSCODE_OVERLOADS_FIRST = """**1** of **2** overloads (use the ↑ ↓ keys to navigate):

<div class="highlight"><pre>
foo_bar(<span style="font-weight: bold; text-decoration: underline">value</span>: int) -&gt; None
</pre></div>
A number to foobar on
The default function for foobaring"""

VSCODE_OVERLOADS_SECOND = """**2** of **2** overloads (use the ↑ ↓ keys to navigate):

<div class="highlight"><pre>
foo_bar(<span style="font-weight: bold; text-decoration: underline">value</span>: int, multiplier: int) -&gt; None
</pre></div>
A number to foobar on
Foobaring with a multiplier"""

VSCODE_OVERLOADS_SECOND_SECOND_PARAMETER = """**2** of **2** overloads (use the ↑ ↓ keys to navigate):

<div class="highlight"><pre>
foo_bar(value: int, <span style="font-weight: bold; text-decoration: underline">multiplier</span>: int) -&gt; None
</pre></div>
Change foobar to work on larger increments
Foobaring with a multiplier"""


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
            self.assertFalse(help.has_overloads())
            self.assertEqual(content, SUBLIME_SINGLE_SIGNATURE)

    def test_overload(self):
        help = SignatureHelp([signature, signature_overload], language_id)
        self.assertIsNotNone(help)
        if help:
            content = help.build_popup_content()
            self.assertTrue(help.has_overloads())
            self.assertEqual(content, SUBLIME_OVERLOADS_FIRST)

            help.select_signature(1)
            help.select_signature(1)  # verify we don't go out of bounds,
            content = help.build_popup_content()
            self.assertEqual(content, SUBLIME_OVERLOADS_SECOND)


class VsCodeSignatureHelpTests(unittest.TestCase):

    def test_single_signature(self):
        help = SignatureHelp([signature], language_id, highlight_parameter=True)
        self.assertIsNotNone(help)
        if help:
            content = help.build_popup_content()
            self.assertFalse(help.has_overloads())
            self.assertEqual(content, VSCODE_SINGLE_SIGNATURE)

    def test_overload(self):
        help = SignatureHelp([signature, signature_overload], language_id, highlight_parameter=True)
        self.assertIsNotNone(help)
        if help:
            content = help.build_popup_content()
            self.assertTrue(help.has_overloads())
            self.assertEqual(content, VSCODE_OVERLOADS_FIRST)

            help.select_signature(1)
            help.select_signature(1)  # verify we don't go out of bounds,
            content = help.build_popup_content()
            self.assertEqual(content, VSCODE_OVERLOADS_SECOND)

    def test_active_parameter(self):
        help = SignatureHelp([signature, signature_overload], language_id, active_signature=1, active_parameter=1,
                             highlight_parameter=True)
        self.assertIsNotNone(help)
        if help:
            content = help.build_popup_content()
            self.assertTrue(help.has_overloads())
            self.assertEqual(content, VSCODE_OVERLOADS_SECOND_SECOND_PARAMETER)


class ReplaceActiveParameterTests(unittest.TestCase):

    def test_simple(self):
        # BUG: here fun(<-- triggers signature help in a string!
        bold_format = "<b>{}</b>"
        self.assertEqual(replace_active_parameter("def fun(param)", "param",
                                                  highlight_format=bold_format), "def fun(<b>param</b>)")

    def test_matching_substrings(self):
        bold_format = "<b>{}</b>"
        self.assertEqual(replace_active_parameter("def fun(param, parameter)", "param",
                                                  highlight_format=bold_format), "def fun(<b>param</b>, parameter)")
        self.assertEqual(replace_active_parameter("def fun(parameter, param)", "param",
                                                  highlight_format=bold_format), "def fun(parameter, <b>param</b>)")

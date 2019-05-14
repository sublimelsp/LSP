from .signature_help import (
    create_signature_help, SignatureHelp, get_documentation,
    parse_signature_information, ScopeRenderer
)
import unittest

language_id = "python"
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


json_stringify = {
    'activeParameter': 0,
    'signatures': [
        {
            'documentation': 'Converts a JavaScript value to a JavaScript Object Notation (JSON) string.',
            'parameters': [
                {'documentation': 'A JavaScript value, usually an object or array, to be converted.',
                 'label': 'value: any'},
                {'documentation': 'A function that transforms the results.',
                 'label': 'replacer?: (key: string, value: any) => any'},
                {'documentation': """Adds indentation, white space, and line break characters to the return-value
 JSON text to make it easier to read.""", 'label': 'space?: string | number'}
            ],
            'label': """stringify(value: any, replacer?: (key: string, value: any) => any, space?:
 string | number): string"""
        },
        {
            'documentation': 'Converts a JavaScript value to a JavaScript Object Notation (JSON) string.',
            'parameters': [
                {'documentation': 'A JavaScript value, usually an object or array, to be converted.',
                 'label': 'value: any'},
                {'documentation': """An array of strings and numbers that acts as a approved list for selecting the
object properties that will be stringified.""", 'label': 'replacer?: (string | number)[]'},
                {'documentation': """Adds indentation, white space, and line break characters to the return-value JSON
 text to make it easier to read.""", 'label': 'space?: string | number'}
            ],
            'label': 'stringify(value: any, replacer?: (string | number)[], space?: string | number): string'
        }
    ],
    'activeSignature': 0
}

signature_information = parse_signature_information(signature)
signature_overload_information = parse_signature_information(signature_overload)

SINGLE_SIGNATURE = """<div class="highlight"><pre>
<span style="color: #6699cc">foo_bar<span style="color: #5fb3b3">(</span>\
<span style="color: #f99157;font-weight: bold">value</span>: int<span \
style="color: #5fb3b3">)</span> -> None</span>
</pre></div>
<p>The default function for foobaring</p>
<p><b>value</b>: A number to foobar on</p>"""

OVERLOADS_FIRST = """**1** of **2** overloads (use the ↑ ↓ keys to navigate):

<div class="highlight"><pre>
<span style="color: #6699cc">foo_bar<span style="color: #5fb3b3">(</span>\
<span style="color: #f99157;font-weight: bold">value</span>: int\
<span style="color: #5fb3b3">)</span> -> None</span>
</pre></div>
<p>The default function for foobaring</p>
<p><b>value</b>: A number to foobar on</p>"""


OVERLOADS_SECOND = """**2** of **2** overloads (use the ↑ ↓ keys to navigate):

<div class="highlight"><pre>
<span style="color: #6699cc">foo_bar<span style="color: #5fb3b3">(</span>\
<span style="color: #f99157;font-weight: bold">value</span>: int, \
<span style="color: #f99157">multiplier</span>: int<span style="color: #5fb3b3">)\
</span> -> None</span>
</pre></div>
<p>Foobaring with a multiplier</p>
<p><b>value</b>: A number to foobar on</p>"""

OVERLOADS_SECOND_SECOND_PARAMETER = """**2** of **2** overloads (use the ↑ ↓ keys to navigate):

<div class="highlight"><pre>
<span style="color: #6699cc">foo_bar<span style="color: #5fb3b3">(</span><span style="color: #f99157">value</span>\
: int, <span style="color: #f99157;font-weight: bold">multiplier</span>: int<span style="color: #5fb3b3">)</span>\
 -> None</span>
</pre></div>
<p>Foobaring with a multiplier</p>
<p><b>multiplier</b>: Change foobar to work on larger increments</p>"""


class TestRenderer(ScopeRenderer):
    def __init__(self) -> None:
        self._scope_styles = {
            'entity.name.function': {'background': '#1b2b34', 'color': '#6699cc', 'style': ''},
            'variable.parameter': {'background': '#1b2b34', 'color': '#f99157', 'style': ''},
            'punctuation': {'background': '#1b2b34', 'color': '#5fb3b3', 'style': ''}
        }

    def render_function(self, content: str) -> str:
        return self._wrap_with_scope_style(content, "entity.name.function")

    def render_punctuation(self, content: str) -> str:
        return self._wrap_with_scope_style(content, "punctuation")

    def render_parameter(self, content: str, emphasize: bool = False) -> str:
        return self._wrap_with_scope_style(content, "variable.parameter", emphasize)

    def _wrap_with_scope_style(self, content: str, scope: str, emphasize: bool = False) -> str:
        color = self._scope_styles[scope]["color"]
        weight_style = ';font-weight: bold' if emphasize else ''
        return '<span style="color: {}{}">{}</span>'.format(color, weight_style, content)


renderer = TestRenderer()


class GetDocumentationTests(unittest.TestCase):

    def test_absent(self):
        self.assertIsNone(get_documentation({}))

    def test_is_str(self):
        self.assertEqual(get_documentation({'documentation': 'str'}), 'str')

    def test_is_dict(self):
        self.assertEqual(get_documentation({'documentation': {'value': 'value'}}), 'value')


class CreateSignatureHelpTests(unittest.TestCase):

    def test_none(self):
        self.assertIsNone(create_signature_help(None, renderer))

    def test_empty(self):
        self.assertIsNone(create_signature_help({}, renderer))

    def test_default_indices(self):

        help = create_signature_help({"signatures": [signature]}, renderer)

        self.assertIsNotNone(help)
        if help:
            self.assertEqual(help._active_signature_index, 0)
            self.assertEqual(help._active_parameter_index, -1)


class SignatureHelpTests(unittest.TestCase):

    def test_single_signature(self):
        renderer
        help = SignatureHelp([signature_information], renderer)
        self.assertIsNotNone(help)
        if help:
            content = help.build_popup_content()
            self.assertFalse(help.has_overloads())
            self.assertEqual(content, SINGLE_SIGNATURE)

    def test_overload(self):
        help = SignatureHelp([signature_information, signature_overload_information],
                             renderer)
        self.assertIsNotNone(help)
        if help:
            content = help.build_popup_content()
            self.assertTrue(help.has_overloads())
            self.assertEqual(content, OVERLOADS_FIRST)

            help.select_signature(1)
            help.select_signature(1)  # verify we don't go out of bounds,
            content = help.build_popup_content()
            self.assertEqual(content, OVERLOADS_SECOND)

    def test_active_parameter(self):
        help = SignatureHelp([signature_information, signature_overload_information], renderer, active_signature=1,
                             active_parameter=1)
        self.assertIsNotNone(help)
        if help:
            content = help.build_popup_content()
            self.assertTrue(help.has_overloads())
            self.assertEqual(content, OVERLOADS_SECOND_SECOND_PARAMETER)

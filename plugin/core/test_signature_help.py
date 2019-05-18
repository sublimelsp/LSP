from .signature_help import (
    create_signature_help, SignatureHelp, get_documentation,
    parse_signature_information, ScopeRenderer, render_signature_label
)
import unittest

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

signature_information = parse_signature_information(signature)
signature_overload_information = parse_signature_information(signature_overload)

SINGLE_SIGNATURE = """<div class="highlight"><pre>

<entity.name.function>foo_bar
<punctuation>(</punctuation>
<variable.parameter emphasize>value</variable.parameter>: int
<punctuation>)</punctuation> -&gt; None</entity.name.function>
</pre></div>
<p>The default function for foobaring</p>
<p><b>value</b>: A number to foobar on</p>"""

OVERLOADS_FIRST = """**1** of **2** overloads (use the ↑ ↓ keys to navigate):

<div class="highlight"><pre>

<entity.name.function>foo_bar
<punctuation>(</punctuation>
<variable.parameter emphasize>value</variable.parameter>: int
<punctuation>)</punctuation> -&gt; None</entity.name.function>
</pre></div>
<p>The default function for foobaring</p>
<p><b>value</b>: A number to foobar on</p>"""


OVERLOADS_SECOND = """**2** of **2** overloads (use the ↑ ↓ keys to navigate):

<div class="highlight"><pre>

<entity.name.function>foo_bar
<punctuation>(</punctuation>
<variable.parameter emphasize>value</variable.parameter>: int,\
 \n<variable.parameter>multiplier</variable.parameter>: int
<punctuation>)</punctuation> -&gt; None</entity.name.function>
</pre></div>
<p>Foobaring with a multiplier</p>
<p><b>value</b>: A number to foobar on</p>"""

OVERLOADS_SECOND_SECOND_PARAMETER = """**2** of **2** overloads (use the ↑ ↓ keys to navigate):

<div class="highlight"><pre>

<entity.name.function>foo_bar
<punctuation>(</punctuation>
<variable.parameter>value</variable.parameter>: int,\
 \n<variable.parameter emphasize>multiplier</variable.parameter>: int
<punctuation>)</punctuation> -&gt; None</entity.name.function>
</pre></div>
<p>Foobaring with a multiplier</p>
<p><b>multiplier</b>: Change foobar to work on larger increments</p>"""


JSON_STRINGIFY = """"""


def create_signature(label: str, *param_labels, **kwargs) -> dict:
    raw = dict(label=label, parameters=list(dict(label=param_label) for param_label in param_labels))
    raw.update(kwargs)
    return raw


class TestRenderer(ScopeRenderer):

    def function(self, content: str, escape: bool = True) -> str:
        return self._wrap_with_scope_style(content, "entity.name.function")

    def punctuation(self, content: str) -> str:
        return self._wrap_with_scope_style(content, "punctuation")

    def parameter(self, content: str, emphasize: bool = False) -> str:
        return self._wrap_with_scope_style(content, "variable.parameter", emphasize)

    def _wrap_with_scope_style(self, content: str, scope: str, emphasize: bool = False) -> str:
        return '\n<{}{}>{}</{}>'.format(scope, " emphasize" if emphasize else "", content, scope)


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
        self.assertIsNone(create_signature_help(None))

    def test_empty(self):
        self.assertIsNone(create_signature_help({}))

    def test_default_indices(self):

        help = create_signature_help({"signatures": [signature]})

        self.assertIsNotNone(help)
        if help:
            self.assertEqual(help._active_signature_index, 0)
            self.assertEqual(help._active_parameter_index, -1)


class RenderSignatureLabelTests(unittest.TestCase):

    def test_no_parameters(self):
        sig = create_signature("foobar()")
        help = create_signature_help(dict(signatures=[sig]))
        if help:
            label = render_signature_label(renderer, help.active_signature(), 0)
            self.assertEqual(label, "\n<entity.name.function>foobar()</entity.name.function>")

    def test_params(self):
        sig = create_signature("foobar(foo, foo)", "foo", "foo", activeParameter=1)
        help = create_signature_help(dict(signatures=[sig]))
        if help:
            label = render_signature_label(renderer, help.active_signature(), 1)
            self.assertEqual(label, """
<entity.name.function>foobar
<punctuation>(</punctuation>
<variable.parameter>foo</variable.parameter>,\
 \n<variable.parameter emphasize>foo</variable.parameter>
<punctuation>)</punctuation></entity.name.function>""")

    def test_params_are_substrings(self):
        sig = create_signature("foobar(self, foo: str, foo: i32)", "foo", "foo", activeParameter=1)
        help = create_signature_help(dict(signatures=[sig]))
        if help:
            label = render_signature_label(renderer, help.active_signature(), 1)
            self.assertEqual(label, """
<entity.name.function>foobar
<punctuation>(</punctuation>self,\
 \n<variable.parameter>foo</variable.parameter>: str,\
 \n<variable.parameter emphasize>foo</variable.parameter>: i32
<punctuation>)</punctuation></entity.name.function>""")

    def test_params_with_range(self):
        sig = create_signature("foobar(foo, foo)", [7, 10], [12, 15], activeParameter=1)
        help = create_signature_help(dict(signatures=[sig]))
        if help:
            label = render_signature_label(renderer, help.active_signature(), 1)
            self.assertEqual(label, """
<entity.name.function>foobar
<punctuation>(</punctuation>
<variable.parameter>foo</variable.parameter>,\
 \n<variable.parameter emphasize>foo</variable.parameter>
<punctuation>)</punctuation></entity.name.function>""")

    def test_params_no_parens(self):
        # note: will not work without ranges: first "foo" param will match "foobar"
        sig = create_signature("foobar foo foo", [7, 10], [11, 14], activeParameter=1)
        help = create_signature_help(dict(signatures=[sig]))
        if help:
            label = render_signature_label(renderer, help.active_signature(), 1)
            self.assertEqual(label, """
<entity.name.function>foobar\
 \n<variable.parameter>foo</variable.parameter>\
 \n<variable.parameter emphasize>foo</variable.parameter></entity.name.function>""")

    def test_escape_content(self):
        sig = create_signature("foobar<T>(foo: Option<i32>) -> List<T>", "foo: Option<i32>", activeParameter=0)
        help = create_signature_help(dict(signatures=[sig]))
        if help:
            label = render_signature_label(renderer, help.active_signature(), 0)
            self.assertEqual(label, """
<entity.name.function>foobar&lt;T&gt;
<punctuation>(</punctuation>
<variable.parameter emphasize>foo: Option&lt;i32&gt;</variable.parameter>
<punctuation>)</punctuation> -&gt; List&lt;T&gt;</entity.name.function>""")


class SignatureHelpTests(unittest.TestCase):

    def test_single_signature(self):
        help = SignatureHelp([signature_information])
        self.assertIsNotNone(help)
        if help:
            content = help.build_popup_content(renderer)
            self.assertFalse(help.has_multiple_signatures())
            self.assertEqual(content, SINGLE_SIGNATURE)

    def test_overload(self):
        help = SignatureHelp([signature_information, signature_overload_information])
        self.assertIsNotNone(help)
        if help:
            content = help.build_popup_content(renderer)
            self.assertTrue(help.has_multiple_signatures())
            self.assertEqual(content, OVERLOADS_FIRST)

            help.select_signature(1)
            help.select_signature(1)  # verify we don't go out of bounds,
            content = help.build_popup_content(renderer)
            self.assertEqual(content, OVERLOADS_SECOND)

    def test_active_parameter(self):
        help = SignatureHelp([signature_information, signature_overload_information], active_signature=1,
                             active_parameter=1)
        self.assertIsNotNone(help)
        if help:
            content = help.build_popup_content(renderer)
            self.assertTrue(help.has_multiple_signatures())
            self.assertEqual(content, OVERLOADS_SECOND_SECOND_PARAMETER)

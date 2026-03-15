from __future__ import annotations

from LSP.plugin.core.signature_help import SigHelp
from LSP.plugin.core.signature_help import SignatureHelpStyle
from LSP.protocol import MarkupKind
from LSP.protocol import SignatureHelp
import re
import sublime
import unittest


class SignatureHelpTest(unittest.TestCase):

    def setUp(self) -> None:
        self.view = sublime.active_window().active_view()
        self.style: SignatureHelpStyle = {
            'function_color': '#ffffff',
            'active_parameter_color': '#ffffff',
            'active_parameter_bold': True,
            'active_parameter_italic': False,
            'active_parameter_underline': False,
            'inactive_parameter_color': '#ffffff'
        }

    def test_no_signature(self) -> None:
        signature = SigHelp.from_lsp(None, None, self.style)
        self.assertIsNone(signature)

    def test_empty_signature_list(self) -> None:
        signature = SigHelp.from_lsp({"signatures": []}, None, self.style)
        self.assertIsNone(signature)

    def assert_render(self, signature_input: SignatureHelp, regex: str) -> None:
        signature = SigHelp(signature_input, None, self.style)
        assert self.view
        # Remove newlines and any 2+ consecutive spaces to make pattern easier to write but match the rendered input.
        pattern = re.sub(r' {2,}', '', regex.replace("\n", ""))
        self.assertRegex(signature.render(self.view), pattern)

    def test_signature(self) -> None:
        self.assert_render(
            {
                "signatures":
                [
                    {
                        "label": "f(x)",
                        "documentation": "f does interesting things",
                        "parameters":
                        [
                            {
                                "label": "x",
                                "documentation": "must be in the frobnicate range"
                            }
                        ]
                    }
                ],
                "activeSignature": 0,
                "activeParameter": 0
            },
            r'''
            <div class="[^"]+">
                <div class="highlight">
                    <span style="color: #\w{6}">f\(</span>
                    <span style="color: #\w{6}; font-weight: bold">x</span>
                    <span style="color: #\w{6}">\)</span>
                </div>
                <span>must be in the frobnicate range</span>
                <div class="wrapper--spacer"></div>
            </div>
            <hr[^>]*>
            <div class="[^"]+">
                <span>f does interesting things</span>
                <div class="wrapper--spacer"></div>
            </div>
            '''
        )

    def test_markdown(self) -> None:
        self.assert_render(
            {
                "signatures":
                [
                    {
                        "label": "f(x)",
                        "documentation":
                        {
                            "value": "f does _interesting_ things",
                            "kind": MarkupKind.Markdown
                        },
                        "parameters":
                        [
                            {
                                "label": "x",
                                "documentation":
                                {
                                    "value": "must be in the **frobnicate** range",
                                    "kind": MarkupKind.Markdown
                                }
                            }
                        ]
                    }
                ],
                "activeSignature": 0,
                "activeParameter": 0
            },
            r'''
            <div class="[^"]+">
                <div class="highlight">
                    <span style="color: #\w{6}">f\(</span>
                    <span style="color: #\w{6}; font-weight: bold">x</span>
                    <span style="color: #\w{6}">\)</span>
                </div>
                <p>must be in the <strong>frobnicate</strong> range</p>
                <div class="wrapper--spacer"></div>
            </div>
            <hr[^>]*>
            <div class="[^"]+">
                <p>f does <em>interesting</em> things</p>
                <div class="wrapper--spacer"></div>
            </div>
            '''
        )

    def test_second_parameter(self) -> None:
        self.assert_render(
            {
                "signatures":
                [
                    {
                        "label": "f(x, y)",
                        "parameters":
                        [
                            {
                                "label": "x"
                            },
                            {
                                "label": "y",
                                "documentation": "hello there"
                            }
                        ]
                    }
                ],
                "activeSignature": 0,
                "activeParameter": 1
            },
            r'''
            <div class="[^"]+">
                <div class="highlight">
                    <span style="color: #\w{6}">f\(</span>
                    <span style="color: #\w{6}">x</span>
                    <span style="color: #\w{6}">, </span>
                    <span style="color: #\w{6}; font-weight: bold">y</span>
                    <span style="color: #\w{6}">\)</span>
                </div>
                <span>hello there</span>
                <div class="wrapper--spacer"></div>
            </div>
            '''
        )

    def test_parameter_ranges(self) -> None:
        self.assert_render(
            {
                "signatures":
                [
                    {
                        "label": "f(x, y)",
                        "parameters":
                        [
                            {
                                "label": [2, 3],
                            },
                            {
                                "label": [5, 6],
                                "documentation": "hello there"
                            }
                        ]
                    }
                ],
                "activeSignature": 0,
                "activeParameter": 1
            },
            r'''
            <div class="[^"]+">
                <div class="highlight">
                    <span style="color: #\w{6}">f\(</span>
                    <span style="color: #\w{6}">x</span>
                    <span style="color: #\w{6}">, </span>
                    <span style="color: #\w{6}; font-weight: bold">y</span>
                    <span style="color: #\w{6}">\)</span>
                </div>
                <span>hello there</span>
                <div class="wrapper--spacer"></div>
            </div>
            '''
        )

    def test_overloads(self) -> None:
        self.assert_render(
            {
                "signatures":
                [
                    {
                        "label": "f(x, y)",
                        "parameters":
                        [
                            {
                                "label": [2, 3]
                            },
                            {
                                "label": [5, 6],
                                "documentation": "hello there"
                            }
                        ]
                    },
                    {
                        "label": "f(x, a, b)",
                        "parameters":
                        [
                            {
                                "label": [2, 3]
                            },
                            {
                                "label": [5, 6]
                            },
                            {
                                "label": [8, 9]
                            }
                        ]
                    }
                ],
                "activeSignature": 1,
                "activeParameter": 0
            },
            r'''
            <div class="[^"]+">
                <p>
                    <b>2</b> of <b>2</b> overloads \(use <kbd>↑</kbd> <kbd>↓</kbd> to navigate, press <kbd>Esc</kbd> to hide\)
                </p>
                <div class="highlight">
                    <span style="color: #\w{6}">f\(</span>
                    <span style="color: #\w{6}; font-weight: bold">x</span>
                    <span style="color: #\w{6}">, </span>
                    <span style="color: #\w{6}">a</span>
                    <span style="color: #\w{6}">, </span>
                    <span style="color: #\w{6}">b</span>
                    <span style="color: #\w{6}">\)</span>
                </div>
                <div class="wrapper--spacer">
            </div>
            '''  # noqa: E501
        )

    def test_dockerfile_signature(self) -> None:
        self.assert_render(
            {
                "signatures":
                [
                    {
                        "label": 'RUN [ "command" "parameters", ... ]',
                        "parameters":
                        [
                            {'label': '['},
                            {'label': '"command"'},
                            {'label': '"parameters"'},
                            {'label': '...'},
                            {'label': ']'}
                        ]
                    }
                ],
                "activeSignature": 0,
                "activeParameter": 2
            },
            r'''
            <div class="[^"]+">
                <span style="color: #\w{6}">RUN </span>
                <span style="color: #\w{6}">\[</span>
                <span style="color: #\w{6}"> </span>
                <span style="color: #\w{6}">"command"</span>
                <span style="color: #\w{6}"> </span>
                <span style="color: #\w{6}; font-weight: bold">"parameters"</span>
                <span style="color: #\w{6}">, </span>
                <span style="color: #\w{6}">\.\.\.</span>
                <span style="color: #\w{6}"> </span>
                <span style="color: #\w{6}">\]</span>
            </div>
            '''
        )

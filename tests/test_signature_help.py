from __future__ import annotations

from LSP.plugin.core.signature_help import SigHelp
from LSP.plugin.core.signature_help import SignatureHelpStyle
from LSP.protocol import SignatureHelp
import sublime
import unittest


class SignatureHelpTest(unittest.TestCase):

    def setUp(self) -> None:
        self.view = sublime.active_window().active_view()
        self.style: SignatureHelpStyle = {
            'function_color': '#ffffff',
            'active_parameter_color': '#ffffff',
            'active_parameter_bold': True,
            'active_parameter_underline': True,
            'inactive_parameter_color': '#ffffff'
        }

    def test_no_signature(self) -> None:
        help = SigHelp.from_lsp(None, None, self.style)
        self.assertIsNone(help)

    def test_empty_signature_list(self) -> None:
        help = SigHelp.from_lsp({"signatures": []}, None, self.style)
        self.assertIsNone(help)

    def assert_render(self, input: SignatureHelp, regex: str) -> None:
        help = SigHelp(input, None, self.style)
        assert self.view
        self.assertRegex(help.render(self.view), regex.replace("\n", "").replace("            ", ""))

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
            <div class="highlight"><pre>
            <span style="color: #\w{6}">f\(</span>
            <span style="color: #\w{6}; font-weight: bold; text-decoration: underline">x</span>
            <span style="color: #\w{6}">\)</span>
            </pre></div>
            <p>must be in the frobnicate range</p>
            <hr/>
            <div style="font-size: 0\.9rem"><p>f does interesting things</p></div>
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
                            "kind": "markdown"
                        },
                        "parameters":
                        [
                            {
                                "label": "x",
                                "documentation":
                                {
                                    "value": "must be in the **frobnicate** range",
                                    "kind": "markdown"
                                }
                            }
                        ]
                    }
                ],
                "activeSignature": 0,
                "activeParameter": 0
            },
            r'''
            <div class="highlight"><pre>
            <span style="color: #\w{6}">f\(</span>
            <span style="color: #\w{6}; font-weight: bold; text-decoration: underline">x</span>
            <span style="color: #\w{6}">\)</span>
            </pre></div>
            <p>must be in the <strong>frobnicate</strong> range</p>
            <hr/>
            <div style="font-size: 0\.9rem"><p>f does <em>interesting</em> things</p></div>
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
            <div class="highlight"><pre>
            <span style="color: #\w{6}">f\(</span>
            <span style="color: #\w{6}">x</span>
            <span style="color: #\w{6}">, </span>
            <span style="color: #\w{6}; font-weight: bold; text-decoration: underline">y</span>
            <span style="color: #\w{6}">\)</span>
            </pre></div>
            <p>hello there</p>
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
            <div class="highlight"><pre>
            <span style="color: #\w{6}">f\(</span>
            <span style="color: #\w{6}">x</span>
            <span style="color: #\w{6}">, </span>
            <span style="color: #\w{6}; font-weight: bold; text-decoration: underline">y</span>
            <span style="color: #\w{6}">\)</span>
            </pre></div>
            <p>hello there</p>
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
            <p>
            <div style="font-size: 0\.9rem">
            <b>2</b> of <b>2</b> overloads \(use <kbd>↑</kbd> <kbd>↓</kbd> to navigate, press <kbd>Esc</kbd> to hide\):
            </div>
            </p>
            <div class="highlight"><pre><span style="color: #\w{6}">f\(</span>
            <span style="color: #\w{6}; font-weight: bold; text-decoration: underline">x</span>
            <span style="color: #\w{6}">, </span>
            <span style="color: #\w{6}">a</span>
            <span style="color: #\w{6}">, </span>
            <span style="color: #\w{6}">b</span>
            <span style="color: #\w{6}">\)</span>
            </pre></div>
            '''
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
            <div class="highlight"><pre>
            <span style="color: #\w{6}">RUN </span>
            <span style="color: #\w{6}">\[</span>
            <span style="color: #\w{6}"> </span>
            <span style="color: #\w{6}">"command"</span>
            <span style="color: #\w{6}"> </span>
            <span style="color: #\w{6}; font-weight: bold; text-decoration: underline">"parameters"</span>
            <span style="color: #\w{6}">, </span>
            <span style="color: #\w{6}">\.\.\.</span>
            <span style="color: #\w{6}"> </span>
            <span style="color: #\w{6}">\]</span>
            </pre></div>
            '''
        )

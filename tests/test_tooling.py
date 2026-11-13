from __future__ import annotations

from .setup import make_stdio_test_config
from .setup import SublimeAioTestCase
from LSP.plugin.tooling import ServerTestRunner
import asyncio
import os
import sublime


class ToolingTestCase(SublimeAioTestCase):
    async def setUp(self) -> None:
        config = make_stdio_test_config("foo")
        window = sublime.active_window()
        view = window.active_view()
        assert view
        assert view.is_valid()
        self.assertIsNotNone(view)
        self.assertTrue(view.is_valid())
        self.resolved_command: list[str] | None = None
        self.cwd: str | None = None
        self.output: str = ""
        self.exit_code: int | None = None
        self.on_close_call_count = 0
        self.on_close_event = asyncio.Event()
        loop = asyncio.get_running_loop()

        def on_close(resolved_command: list[str] | None, cwd: str | None, output: str, exit_code: int) -> None:

            def on_close_on_loop_thread() -> None:
                self.resolved_command = resolved_command
                self.cwd = cwd
                self.output = output
                self.exit_code = exit_code
                self.on_close_call_count += 1
                self.on_close_event.set()

            loop.call_soon_threadsafe(on_close_on_loop_thread)

        self.runner = ServerTestRunner(config, window, view, on_close)

    async def test_on_close_is_called_once(self) -> None:
        await self.runner.run(close_timeout_sec=0.5)
        await self.on_close_event.wait()
        rootdir = sublime.expand_variables(
            os.path.join("$packages", "LSP"), sublime.active_window().extract_variables()
        )
        self.assertEqual(self.resolved_command, ["python3", os.path.join(rootdir, "tests", "server.py")])
        self.assertEqual(self.exit_code, 1)
        self.assertEqual(self.on_close_call_count, 1)

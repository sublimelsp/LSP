from io import BytesIO
from LSP.plugin.core.process import log_stream
from unittest import TestCase
from unittest.mock import MagicMock
import os
import subprocess

try:
    from typing import Iterator
    from typing import Tuple
    assert Iterator and Tuple
except ImportError:
    pass


class ProcessTests(TestCase):

    def test_log_stream_encoding_utf8(self):
        encoding = 'UTF-8'
        si = None
        if os.name == "nt":
            si = subprocess.STARTUPINFO()  # type: ignore
            si.dwFlags |= subprocess.SW_HIDE | subprocess.STARTF_USESHOWWINDOW  # type: ignore
        process = subprocess.Popen(args=['cmd.exe' if os.name == 'nt' else 'bash'], bufsize=1024, startupinfo=si)
        process.poll = MagicMock(return_value=None)  # type: ignore
        text = '\U00010000'
        message = ""

        def log_callback(msg: str) -> None:
            nonlocal message
            message = msg

        log_stream(process, BytesIO(text.encode(encoding)), log_callback)
        self.assertEqual(message.strip(), text)
        process.kill()

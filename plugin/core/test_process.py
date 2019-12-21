from .process import log_stream
from io import BytesIO
from subprocess import Popen
from unittest import TestCase
from unittest.mock import MagicMock
import os

try:
    from typing import Iterator
    from typing import Tuple
    assert Iterator and Tuple
except ImportError:
    pass


class ProcessTests(TestCase):

    def test_log_stream_encoding_utf8(self):
        encoding = 'UTF-8'
        process = Popen(args=['cmd.exe' if os.name == 'nt' else 'bash'], bufsize=1024)
        process.poll = MagicMock(return_value=None)  # type: ignore
        text = '\U00010000'
        message = ""

        def log_callback(msg: str) -> None:
            nonlocal message
            message = msg

        log_stream(process, BytesIO(text.encode(encoding)), log_callback)
        self.assertEqual(message.strip(), text)

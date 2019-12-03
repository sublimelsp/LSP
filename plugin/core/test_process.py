from .process import log_stream
from contextlib import contextmanager
from io import BytesIO
from io import StringIO
from subprocess import Popen
from unittest import TestCase
from unittest.mock import MagicMock
import os
import sys

try:
    from typing import Iterator
    from typing import Tuple
    assert Iterator and Tuple
except ImportError:
    pass


@contextmanager
def captured_output() -> 'Iterator[Tuple[StringIO, StringIO]]':
    new_out, new_err = StringIO(), StringIO()
    old_out, old_err = sys.stdout, sys.stderr
    try:
        sys.stdout, sys.stderr = new_out, new_err
        yield sys.stdout, sys.stderr
    finally:
        sys.stdout, sys.stderr = old_out, old_err


class ProcessTests(TestCase):

    def test_log_stream_encoding_utf8(self):
        encoding = 'UTF-8'
        process = Popen(args=['cmd.exe' if os.name == 'nt' else 'bash'], bufsize=1024)
        process.poll = MagicMock(return_value=None)  # type: ignore
        text = '\U00010000'
        with captured_output() as (out, err):
            log_stream(process, BytesIO(text.encode(encoding)))
        self.assertEqual(out.getvalue().strip(), 'server: {}'.format(text))
        self.assertEqual(err.getvalue().strip(), '')

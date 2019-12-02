from .process import log_stream
from contextlib import contextmanager
from io import BytesIO, StringIO
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

    def do_test(self, encoded: bytes, expected: str):
        process = Popen(args=['cmd.exe' if os.name == 'nt' else 'bash'], bufsize=1024)
        process.poll = MagicMock(return_value=None)  # type: ignore
        stream = BytesIO(encoded)
        with captured_output() as (out, err):
            log_stream(process, stream)
        self.assertEqual(out.getvalue().strip(), 'server: {}'.format(expected))
        self.assertEqual(err.getvalue().strip(), '')

    def test_log_stream_encoding_utf8(self):
        # The unicode character
        #
        #    U+10000
        #
        # is encoded in UTF-8 as
        #
        #    0xF0 0x90 0x80 0x80
        #
        #  and in UTF-16 as
        #
        #    0xD800 0xDC00
        #
        # So let's use that character to do our tests. https://www.compart.com/en/unicode/U+10000
        encoded_input = bytes((0xF0, 0x90, 0x80, 0x80))
        expected_output = '\U00010000'
        self.do_test(encoded_input, expected_output)

    def test_log_stream_encoding_utf16(self):
        # Here we encode U+10000 as something that can't be decoded by UTF-8, so log_stream should try to decode it as
        # UTF-16 instead.
        encoded_input = bytes((0x00, 0xD8, 0x00, 0xDC))  # little endian...
        expected_output = '\U00010000'
        self.do_test(encoded_input, expected_output)

    def test_log_stream_encoding_failure(self):
        encoded_input = bytes((0x00, 0xD8, 0x00))
        expected_output = 'Unable to decode bytes! (tried UTF-8 and UTF-16)'
        self.do_test(encoded_input, expected_output)

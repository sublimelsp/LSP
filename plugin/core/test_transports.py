import unittest
import io
from .transports import StdioTransport, TCPTransport
import time


def json_rpc_message(payload: str) -> bytes:
    content_length = len(payload)
    return b'Content-Length: ' + bytes(
        str(content_length), 'utf-8') + b'\r\n\r\n' + bytes(payload, 'utf-8')


class FakeProcess(object):
    def __init__(self):
        self.stdin = io.BytesIO(b'foo\nbaz\n')  # io.BufferedReader()
        self.stdout = io.BytesIO(
            json_rpc_message("hello") +
            json_rpc_message("world"))  # io.BufferedWriter()
        self.returncode = None

    def poll(self):
        return self.returncode

    def exit(self, returncode):
        self.returncode = returncode


class FakeSocket(object):
    def __init__(self, data: bytes) -> None:
        self.data = data
        self.index = 0

    def recv(self, length: int) -> bytes:
        slc = self.data[self.index:length]
        self.index = max(len(self.data), self.index + length)
        return slc

    def sendall(self, payload: bytes) -> None:
        pass


class StdioTransportTests(unittest.TestCase):
    def test_read_messages(self):

        process = FakeProcess()
        t = StdioTransport(process)  # type: ignore
        self.assertIsNotNone(t)
        received = []

        def on_receive(msg):
            received.append(msg)

        def on_close():
            pass

        t.start(on_receive, on_close)
        time.sleep(0.01)
        self.assertEqual(received, ["hello", "world"])
        t.close()


class TCPTransportTests(unittest.TestCase):
    def test_read_messages(self):
        sock = FakeSocket(
            json_rpc_message("hello") + json_rpc_message("world"))
        t = TCPTransport(sock)
        self.assertIsNotNone(t)
        received = []

        def on_receive(msg):
            received.append(msg)

        def on_close():
            pass

        t.start(on_receive, on_close)
        time.sleep(0.01)
        self.assertEqual(received, ["hello", "world"])
        t.close()

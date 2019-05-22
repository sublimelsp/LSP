import unittest
import io
from .transports import StdioTransport, TCPTransport
import time
try:
    from typing import List
    assert List
except ImportError:
    pass


def json_rpc_message(payload: str) -> bytes:
    content_length = len(payload)
    return b'Content-Length: ' + bytes(
        str(content_length), 'utf-8') + b'\r\n\r\n' + bytes(payload, 'utf-8')


class FakeProcess(object):
    def __init__(self):
        self.stdin = io.BytesIO(b'')  # io.BufferedReader()
        self.stdout = io.BytesIO(
            json_rpc_message("hello") +
            json_rpc_message("world"))  # io.BufferedWriter()
        self.returncode = None

    def poll(self):
        return self.returncode

    def exit(self, returncode):
        self.returncode = returncode


class FakeSocket(object):
    def __init__(self, received: bytes) -> None:
        self.received = received
        self.sent = []  # type: List[str]
        self.index = 0

    def recv(self, length: int) -> bytes:
        slc = self.received[self.index:length]
        if slc:
            self.index = max(len(self.received), self.index + length)
            return slc
        else:
            time.sleep(1)  # simulate blocking for the duration of the test.
            return b''

    def sendall(self, payload: str) -> None:
        self.sent.append(payload)


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

    def test_write_messages(self):

        process = FakeProcess()
        t = StdioTransport(process)  # type: ignore
        self.assertIsNotNone(t)
        received = []

        def on_receive(msg):
            received.append(msg)

        def on_close():
            pass

        t.start(on_receive, on_close)
        t.send("hello")
        t.send("world")
        time.sleep(0.01)
        self.assertEqual(process.stdin.getvalue(), b"helloworld")
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

    def test_write_messages(self):
        sock = FakeSocket(b'')
        t = TCPTransport(sock)
        self.assertIsNotNone(t)
        received = []

        def on_receive(msg):
            received.append(msg)

        def on_close():
            pass

        t.start(on_receive, on_close)
        # TODO: move building payload into transport instead of client.
        t.send("hello")
        t.send("world")
        time.sleep(0.1)
        self.assertEqual(sock.sent, [b"hello", b"world"])
        t.close()

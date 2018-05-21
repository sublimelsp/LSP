from .rpc import (format_request, Client, Transport)
from .protocol import (Request)
import unittest

class TestSettings(object):

    def __init__(self):
        self.log_payloads = False


class TestTransport(Transport):
    def __init__(self):
        pass

    def start(self, on_receive, on_closed):
        self.on_receive = on_receive
        self.on_closed = on_closed
        self.has_started = True

    def send(self, message):
        self.on_receive('{"id": 1, "result": {}}')

    def close(self):
        self.on_closed()


class FormatTests(unittest.TestCase):

    def test_converts_payload_to_string(self):
        self.assertEqual("Content-Length: 2\r\n\r\n{}", format_request(dict()))


class ClientTest(unittest.TestCase):

    def test_can_create_client(self):
        transport = TestTransport()
        client = Client(
             None, transport, "", dict()
            )
        self.assertIsNotNone(client)
        self.assertTrue(transport.has_started)

    def test_can_initialize(self):
        transport = TestTransport()
        settings = TestSettings()
        client = Client(
             None, transport, "", settings
            )
        self.assertIsNotNone(client)
        self.assertTrue(transport.has_started)
        req = Request.initialize(dict())
        responses = []
        # responded = False
        client.send_request(req, lambda resp: responses.append(resp))
        self.assertGreater(len(responses), 0)




    # def test_can_
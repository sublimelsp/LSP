from .rpc import (format_request, Client)
from .transports import Transport
from .protocol import (Request, Notification)
from .types import Settings
import unittest
import json
try:
    from typing import Any, List, Dict, Tuple, Callable, Optional
    assert Any and List and Dict and Tuple and Callable and Optional
except ImportError:
    pass


class TestSettings(Settings):

    def __init__(self):
        Settings.__init__(self)
        self.log_payloads = False


def return_result(message):
    return '{"id": 1, "result": {}}'

    # parsed = json.loads(message)
    # request_id = parsed.get("id")
    # if request_id is not None:
    #     return '{"id": ' + str(request_id) + ', "result": {}}'


def return_error(message):
    return '{"id": 1, "error": {"message": "oops"}}'


def raise_error(message):
    raise Exception(message)


def notify_pong(message):
    notification = {
        "method": "pong"
    }
    return json.dumps(notification)


class TestTransport(Transport):
    def __init__(self, responder=None):
        self.messages = []  # type: List[str]
        self.responder = responder

    def start(self, on_receive, on_closed):
        self.on_receive = on_receive
        self.on_closed = on_closed
        self.has_started = True

    def send(self, message):
        self.messages.append(message)
        if self.responder:
            self.on_receive(self.responder(message))

    def receive(self, message):
        self.on_receive(message)

    def close(self):
        self.on_closed()


class FormatTests(unittest.TestCase):

    def test_converts_payload_to_string(self):
        self.assertEqual("Content-Length: 2\r\n\r\n{}", format_request(dict()))


class ClientTest(unittest.TestCase):

    def test_can_create_client(self):
        transport = TestTransport()
        client = Client(transport, dict())
        self.assertIsNotNone(client)
        self.assertTrue(transport.has_started)

    def test_client_request_response(self):
        transport = TestTransport(return_result)
        settings = TestSettings()
        client = Client(transport, settings)
        self.assertIsNotNone(client)
        self.assertTrue(transport.has_started)
        req = Request.initialize(dict())
        responses = []
        client.send_request(req, lambda resp: responses.append(resp))
        self.assertGreater(len(responses), 0)

    def test_client_notification(self):
        transport = TestTransport(notify_pong)
        settings = TestSettings()
        client = Client(transport, settings)
        self.assertIsNotNone(client)
        self.assertTrue(transport.has_started)
        pongs = []
        client.on_notification(
            "pong",
            lambda params: pongs.append(params))

        req = Notification("ping", dict())
        client.send_notification(req)
        self.assertGreater(len(transport.messages), 0)
        self.assertEqual(len(pongs), 1)

    def test_server_request(self):
        # TODO: LSP never responds to eg workspace/applyEdit.

        transport = TestTransport()
        settings = TestSettings()
        client = Client(transport, settings)
        self.assertIsNotNone(client)
        self.assertTrue(transport.has_started)
        pings = []

        client.on_request(
            "ping",
            lambda params: pings.append(params))

        transport.receive('{ "id": 1, "method": "ping"}')
        self.assertEqual(len(pings), 1)

    def test_response_error(self):
        transport = TestTransport(return_error)
        settings = TestSettings()
        client = Client(transport, settings)
        self.assertIsNotNone(client)
        self.assertTrue(transport.has_started)
        req = Request.initialize(dict())
        errors = []
        client.set_error_display_handler(lambda err: errors.append(err))
        responses = []
        client.send_request(req, lambda resp: responses.append(resp))
        self.assertEqual(len(responses), 0)
        self.assertGreater(len(errors), 0)

    def test_forwards_transport_error(self):
        transport = TestTransport(raise_error)
        settings = TestSettings()
        client = Client(transport, settings)
        errors = []
        client.set_transport_failure_handler(lambda: errors.append(""))
        self.assertTrue(transport.has_started)
        responses = []
        req = Request.initialize(dict())
        client.send_request(req, lambda resp: responses.append(resp))
        self.assertEqual(len(responses), 0)
        self.assertGreater(len(errors), 0)

    def test_handles_transport_closed_unexpectedly(self):
        transport = TestTransport(raise_error)
        settings = TestSettings()
        client = Client(transport, settings)
        errors = []
        client.set_transport_failure_handler(lambda: errors.append(""))
        self.assertTrue(transport.has_started)
        transport.close()
        self.assertGreater(len(errors), 0)

    def test_survives_handler_error(self):
        transport = TestTransport(return_result)
        settings = TestSettings()
        client = Client(transport, settings)
        self.assertIsNotNone(client)
        self.assertTrue(transport.has_started)
        req = Request.initialize(dict())
        client.send_request(req, lambda resp: raise_error('handler failed'))
        # exception would fail test if not handled in client

from LSP.plugin.core.logging import set_exception_logging
from LSP.plugin.core.protocol import Notification
from LSP.plugin.core.protocol import Request
from LSP.plugin.core.rpc import Client
from LSP.plugin.core.rpc import format_request
from LSP.plugin.core.transports import Transport
from LSP.plugin.core.types import Settings
from test_mocks import MockSettings
import json
import unittest
try:
    from typing import Any, List, Dict, Tuple, Callable, Optional
    assert Any and List and Dict and Tuple and Callable and Optional
except ImportError:
    pass


def return_empty_dict_result(message):
    return '{"id": 1, "result": {}}'


def return_null_result(message):
    return '{"id": 1, "result": null}'


def return_error(message):
    return '{"id": 1, "error": {"message": "oops"}}'


def raise_error(message):
    raise Exception(message)


def notify_pong(message):
    notification = {
        "method": "pong"
    }
    return json.dumps(notification)


class MockTransport(Transport):
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
        self.assertEqual("{}", format_request(dict()))


class ClientTest(unittest.TestCase):

    def test_can_create_client(self):
        transport = MockTransport()
        client = Client(transport, Settings())
        self.assertIsNotNone(client)
        self.assertTrue(transport.has_started)

    def test_client_request_response(self):
        transport = MockTransport(return_empty_dict_result)
        settings = MockSettings()
        client = Client(transport, settings)
        self.assertIsNotNone(client)
        self.assertTrue(transport.has_started)
        req = Request.initialize(dict())
        responses = []
        client.send_request(req, lambda resp: responses.append(resp))
        self.assertGreater(len(responses), 0)
        # Make sure the response handler dict does not grow.
        self.assertEqual(len(client._response_handlers), 0)

    def test_client_request_with_none_response(self):
        transport = MockTransport(return_null_result)
        settings = MockSettings()
        client = Client(transport, settings)
        self.assertIsNotNone(client)
        self.assertTrue(transport.has_started)
        req = Request.shutdown()
        responses = []
        errors = []
        client.send_request(req, lambda resp: responses.append(resp), lambda err: errors.append(err))
        self.assertEqual(len(responses), 1)
        self.assertEqual(len(errors), 0)

    def test_client_should_reject_response_when_both_result_and_error_are_present(self):
        transport = MockTransport(lambda x: '{"id": 1, "result": {"key": "value"}, "error": {"message": "oops"}}')
        settings = MockSettings()
        client = Client(transport, settings)
        req = Request.initialize(dict())
        responses = []
        errors = []
        client.send_request(req, lambda resp: responses.append(resp), lambda err: errors.append(err))
        self.assertEqual(len(responses), 0)
        self.assertEqual(len(errors), 0)

    def test_client_should_reject_response_when_both_result_and_error_keys_are_not_present(self):
        transport = MockTransport(lambda x: '{"id": 1}')
        settings = MockSettings()
        client = Client(transport, settings)
        req = Request.initialize(dict())
        responses = []
        errors = []
        client.send_request(req, lambda resp: responses.append(resp), lambda err: errors.append(err))
        self.assertEqual(len(responses), 0)
        self.assertEqual(len(errors), 0)

    def test_client_notification(self):
        transport = MockTransport(notify_pong)
        settings = MockSettings()
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
        transport = MockTransport()
        settings = MockSettings()
        client = Client(transport, settings)
        self.assertIsNotNone(client)
        self.assertTrue(transport.has_started)
        pings = []  # type: List[Tuple[int, Dict[str, Any]]]
        client.on_request(
            "ping",
            lambda params, request_id: pings.append((request_id, params)))
        transport.receive('{ "id": 42, "method": "ping"}')
        self.assertEqual(len(pings), 1)
        self.assertEqual(pings[0][0], 42)

    def test_error_response_handler(self):
        transport = MockTransport(return_error)
        settings = MockSettings()
        client = Client(transport, settings)
        self.assertIsNotNone(client)
        self.assertTrue(transport.has_started)
        req = Request.initialize(dict())
        errors = []
        responses = []
        client.send_request(req, lambda resp: responses.append(resp), lambda err: errors.append(err))
        self.assertEqual(len(responses), 0)
        self.assertGreater(len(errors), 0)
        self.assertEqual(len(client._response_handlers), 0)

    def test_error_display_handler(self):
        transport = MockTransport(return_error)
        settings = MockSettings()
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
        self.assertEqual(len(client._response_handlers), 0)

    def test_handles_transport_closed_unexpectedly(self):
        set_exception_logging(False)
        transport = MockTransport(raise_error)
        settings = MockSettings()
        client = Client(transport, settings)
        errors = []
        client.set_transport_failure_handler(lambda: errors.append(""))
        self.assertTrue(transport.has_started)
        transport.close()
        self.assertGreater(len(errors), 0)

    def test_survives_handler_error(self):
        set_exception_logging(False)
        transport = MockTransport(return_empty_dict_result)
        settings = MockSettings()
        client = Client(transport, settings)
        self.assertIsNotNone(client)
        self.assertTrue(transport.has_started)
        req = Request.initialize(dict())
        client.send_request(req, lambda resp: raise_error('handler failed'))
        # exception would fail test if not handled in client
        self.assertEqual(len(client._response_handlers), 0)

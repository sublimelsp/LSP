from LSP.plugin.core.logging import set_exception_logging
from LSP.plugin.core.protocol import Error
from LSP.plugin.core.protocol import ErrorCode
from LSP.plugin.core.protocol import Notification
from LSP.plugin.core.protocol import Request
from LSP.plugin.core.rpc import Client
from LSP.plugin.core.rpc import format_request
from LSP.plugin.core.rpc import SyncRequestStatus
from LSP.plugin.core.transports import Transport
from LSP.plugin.core.types import Settings
<<<<<<< HEAD
from LSP.plugin.core.typing import Any, List, Dict, Tuple
=======
from LSP.plugin.core.typing import List, Tuple, Dict, Any
>>>>>>> master
from test_mocks import MockSettings
import json
import unittest


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


class SyncRequestStatusTest(unittest.TestCase):

    def test_tiny_state_machine(self):
        sync = SyncRequestStatus()
        self.assertTrue(sync.is_idle())
        self.assertFalse(sync.is_requesting())
        self.assertFalse(sync.is_ready())

        sync.prepare(1)
        self.assertFalse(sync.is_idle())
        self.assertTrue(sync.is_requesting())
        self.assertFalse(sync.is_ready())

        sync.set(1, {"foo": "bar"})
        self.assertFalse(sync.is_idle())
        self.assertFalse(sync.is_requesting())
        self.assertTrue(sync.is_ready())
        self.assertFalse(sync.has_error())

        payload = sync.flush()
        self.assertTrue(sync.is_idle())
        self.assertFalse(sync.is_requesting())
        self.assertFalse(sync.is_ready())
        self.assertDictEqual(payload, {"foo": "bar"})

    def test_error_response(self):
        sync = SyncRequestStatus()
        sync.prepare(1)

        sync.set_error(1, {"code": 1243, "message": "everything is broken!"})
        self.assertFalse(sync.is_idle())
        self.assertFalse(sync.is_requesting())
        self.assertTrue(sync.is_ready())
        self.assertTrue(sync.has_error())

        error = sync.flush_error()
        self.assertTrue(sync.is_idle())
        self.assertFalse(sync.is_requesting())
        self.assertFalse(sync.is_ready())
        self.assertDictEqual(error, {"code": 1243, "message": "everything is broken!"})

    def test_exception_during_requesting(self):
        sync = SyncRequestStatus()
        sync.prepare(1)
        try:
            raise RuntimeError("oops")
            sync.set(1234, {"foo": "bar"})  # never reached
        except Exception:
            sync.reset()
        # sync should be usable again
        self.assertTrue(sync.is_idle())
        self.assertFalse(sync.is_requesting())
        self.assertFalse(sync.is_ready())

    def test_assertion_error(self):
        sync = SyncRequestStatus()
        sync.prepare(4321)
        with self.assertRaises(AssertionError):
            sync.set(4322, {"foo": "bar"})


class ClientTest(unittest.TestCase):

    def test_can_create_client(self):
        transport = MockTransport()
        client = Client(transport, Settings())
        self.assertIsNotNone(client)
        self.assertTrue(transport.has_started)

    def do_client_request_response(self, method):
        transport = MockTransport(return_empty_dict_result)
        settings = MockSettings()
        client = Client(transport, settings)
        self.assertIsNotNone(client)
        self.assertTrue(transport.has_started)
        req = Request.initialize(dict())
        responses = []
        do_request = method.__get__(client, Client)
        do_request(req, lambda resp: responses.append(resp))
        self.assertGreater(len(responses), 0)
        # Make sure the response handler dict does not grow.
        self.assertEqual(len(client._response_handlers), 0)

    def test_client_request_response_async(self):
        self.do_client_request_response(Client.send_request)

    def test_client_request_response_sync(self):
        self.do_client_request_response(Client.execute_request)

    def do_client_request_with_none_response(self, method):
        transport = MockTransport(return_null_result)
        settings = MockSettings()
        client = Client(transport, settings)
        self.assertIsNotNone(client)
        self.assertTrue(transport.has_started)
        req = Request.shutdown()
        responses = []
        errors = []
        # https://stackoverflow.com/questions/1015307/python-bind-an-unbound-method
        do_request = method.__get__(client, Client)
        do_request(req, lambda resp: responses.append(resp), lambda err: errors.append(err))
        self.assertEqual(len(responses), 1)
        self.assertEqual(len(errors), 0)

    def test_client_request_with_none_response_async(self):
        self.do_client_request_with_none_response(Client.send_request)

    def test_client_request_with_none_response_sync(self):
        self.do_client_request_with_none_response(Client.execute_request)

    def do_client_should_reject_response_when_both_result_and_error_are_present(self, method):
        transport = MockTransport(lambda x: '{"id": 1, "result": {"key": "value"}, "error": {"message": "oops"}}')
        settings = MockSettings()
        client = Client(transport, settings)
        req = Request.initialize(dict())
        responses = []
        errors = []
        do_request = method.__get__(client, Client)
        do_request(req, lambda resp: responses.append(resp), lambda err: errors.append(err))
        self.assertEqual(len(responses), 0)
        self.assertEqual(len(errors), 0)

    def test_client_should_reject_response_when_both_result_and_error_are_present_async(self):
        self.do_client_should_reject_response_when_both_result_and_error_are_present(Client.send_request)

    def test_client_should_reject_response_when_both_result_and_error_are_present_sync(self):
        self.do_client_should_reject_response_when_both_result_and_error_are_present(Client.execute_request)

    def do_client_should_reject_response_when_both_result_and_error_keys_are_not_present(self, method):
        transport = MockTransport(lambda x: '{"id": 1}')
        settings = MockSettings()
        client = Client(transport, settings)
        req = Request.initialize(dict())
        responses = []
        errors = []
        do_request = method.__get__(client, Client)
        do_request(req, lambda resp: responses.append(resp), lambda err: errors.append(err))
        self.assertEqual(len(responses), 0)
        self.assertEqual(len(errors), 0)

    def test_client_should_reject_response_when_both_result_and_error_keys_are_not_present_async(self):
        self.do_client_should_reject_response_when_both_result_and_error_keys_are_not_present(Client.send_request)

    def test_client_should_reject_response_when_both_result_and_error_keys_are_not_present_sync(self):
        self.do_client_should_reject_response_when_both_result_and_error_keys_are_not_present(Client.execute_request)

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
        pings = []  # type: List[Tuple[Any, Dict[str, Any]]]
        client.on_request(
            "ping",
            lambda params, request_id: pings.append((request_id, params)))
        transport.receive('{ "id": 42, "method": "ping"}')
        self.assertEqual(len(pings), 1)
        self.assertIsInstance(pings[0][0], int)
        self.assertEqual(pings[0][0], 42)

<<<<<<< HEAD
    def do_error_response_handler(self, method):
=======
    def test_server_request_non_integer_request(self):
        transport = MockTransport()
        settings = MockSettings()
        client = Client(transport, settings)
        self.assertIsNotNone(client)
        self.assertTrue(transport.has_started)
        pings = []  # type: List[Tuple[Any, Dict[str, Any]]]
        client.on_request(
            "ping",
            lambda params, request_id: pings.append((request_id, params)))
        transport.receive('{ "id": "abcd-1234-efgh-5678", "method": "ping"}')
        self.assertEqual(len(pings), 1)
        self.assertIsInstance(pings[0][0], str)
        self.assertEqual(pings[0][0], "abcd-1234-efgh-5678")

    def test_server_request_unknown(self):
        transport = MockTransport()
        settings = MockSettings()
        client = Client(transport, settings)
        self.assertIsNotNone(client)
        self.assertTrue(transport.has_started)
        transport.receive('{ "id": "abcd-1234-efgh-5678", "method": "ping"}')
        self.assertEqual(len(transport.messages), 1)
        self.assertEqual(
            json.loads(transport.messages[0]),
            {
                "error": {
                    "message": "ping",
                    "code": -32601
                },
                "jsonrpc": "2.0",
                "id": "abcd-1234-efgh-5678"
            }
        )

    def test_server_request_exception_during_handler(self):
        transport = MockTransport()
        settings = MockSettings()
        client = Client(transport, settings)
        self.assertIsNotNone(client)
        self.assertTrue(transport.has_started)

        def always_raise_exception(params: Any, request_id: Any) -> None:
            raise AttributeError("whoops")

        client.on_request("ping", always_raise_exception)
        transport.receive('{ "id": "abcd-1234-efgh-5678", "method": "ping"}')
        self.assertEqual(len(transport.messages), 1)
        self.assertEqual(
            json.loads(transport.messages[0]),
            {
                "error": {
                    "message": "whoops",
                    "code": -32603
                },
                "jsonrpc": "2.0",
                "id": "abcd-1234-efgh-5678"
            }
        )

    def test_server_request_send_error(self):
        transport = MockTransport()
        settings = MockSettings()
        client = Client(transport, settings)
        self.assertIsNotNone(client)
        self.assertTrue(transport.has_started)

        def always_raise_exception(params: Any, request_id: Any) -> None:
            raise Error(ErrorCode.InvalidParams, "expected dict, got list")

        client.on_request("ping", always_raise_exception)
        transport.receive('{ "id": "abcd-1234-efgh-5678", "method": "ping"}')
        self.assertEqual(len(transport.messages), 1)
        self.assertEqual(
            json.loads(transport.messages[0]),
            {
                "error": {
                    "message": "expected dict, got list",
                    "code": -32602
                },
                "jsonrpc": "2.0",
                "id": "abcd-1234-efgh-5678"
            }
        )

    def test_error_response_handler(self):
>>>>>>> master
        transport = MockTransport(return_error)
        settings = MockSettings()
        client = Client(transport, settings)
        self.assertIsNotNone(client)
        self.assertTrue(transport.has_started)
        req = Request.initialize(dict())
        errors = []
        responses = []
        do_request = method.__get__(client, Client)
        do_request(req, lambda resp: responses.append(resp), lambda err: errors.append(err))
        self.assertEqual(len(responses), 0)
        self.assertGreater(len(errors), 0)
        self.assertEqual(len(client._response_handlers), 0)

    def test_error_response_handler_async(self):
        self.do_error_response_handler(Client.send_request)

    def test_error_response_handler_sync(self):
        self.do_error_response_handler(Client.execute_request)

    def do_error_display_handler(self, method):
        transport = MockTransport(return_error)
        settings = MockSettings()
        client = Client(transport, settings)
        self.assertIsNotNone(client)
        self.assertTrue(transport.has_started)
        req = Request.initialize(dict())
        errors = []
        client.set_error_display_handler(lambda err: errors.append(err))
        responses = []
        do_request = method.__get__(client, Client)
        do_request(req, lambda resp: responses.append(resp))
        self.assertEqual(len(responses), 0)
        self.assertGreater(len(errors), 0)
        self.assertEqual(len(client._response_handlers), 0)

    def test_error_display_handler_async(self):
        self.do_error_display_handler(Client.send_request)

    def test_error_display_handler_sync(self):
        self.do_error_display_handler(Client.execute_request)

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

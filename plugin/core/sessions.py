from .types import ClientConfig, ClientStates
from .protocol import Request, Notification
from .transports import start_tcp_transport, StdioTransport
from .rpc import Client
from .process import start_server


class ClientBootstrapper(object):
    def __init__(self):
        self._callback = None
        pass

    def when_ready(self, receive_client):
        self._callback = receive_client

# todo: make some provider-like pattern so these can be composable?


class TCPOnlyBootstrapper(ClientBootstrapper):
    def __init__(self, port, settings):
        self._port = port
        self._settings = settings

    def when_ready(self, receive_client):
        transport = start_tcp_transport(self._port)
        if transport:
            receive_client(Client(transport, self._settings))


class ProcessManager(object):
    def __init__(self, config: ClientConfig, project_path, env) -> None:
        self._config = config
        self._project_path = project_path
        self._env = env

    def start(self, receive_process):
        # see start_server from main.py - move this to process.py
        receive_process(start_server(self._config, self._project_path, self._env))


class StdioServerBootstrapper(ClientBootstrapper):
    def __init__(self, process_manager, settings):
        self._process_manager = process_manager
        self._client_receiver = None
        self._settings = settings

    def when_ready(self, receive_client):
        self._client_receiver = receive_client
        self._process_manager.start(lambda process: self._receive_process(process))

    def _receive_process(self, process):
        self._client_receiver(Client(StdioTransport(process), self._settings))


class TCPServerBootstrapper(ClientBootstrapper):
    def __init__(self, process_manager, port, settings):
        self._process_manager = process_manager
        self._port = port
        self._client_receiver = None
        self._process = None
        self._settings = settings

    def when_ready(self, receive_client):
        self._client_reciever = receive_client
        self._process_manager.start(lambda process: self._receive_process(process))

    def _receive_process(self, process):
        self._process = process
        transport = start_tcp_transport(self._port)
        self._client_receiver(Client(transport, self._settings))


def create_session(config: ClientConfig, project_path: str, env: dict, settings, bootstrap_client=None) -> 'Session':
    if config.binary_args:
        if config.tcp_port:
            # session = Session(project_path, ClientProvider(TcpTransportProvider(
            # ProcessProvider(config, project_path), config.tcp_port)))
            session = Session(project_path,
                              TCPServerBootstrapper(ProcessManager(config, project_path, env),
                                                    config.tcp_port,
                                                    settings))
        else:
            session = Session(project_path,
                              StdioServerBootstrapper(ProcessManager(config, project_path, env),
                                                      settings))
    else:
        if config.tcp_port:
            session = Session(project_path, TCPOnlyBootstrapper(config.tcp_port, settings))

        if bootstrap_client:
            session = Session(project_path, TestClientBootstrapper(bootstrap_client))
        else:
            session = Session(project_path, ClientBootstrapper())

    return session


class TestClientBootstrapper(ClientBootstrapper):
    def __init__(self, bootstrap_client):
        self._make_client = bootstrap_client

    def when_ready(self, receive_client):
        receive_client(self._make_client())


class Session(object):
    def __init__(self, project_path, bootstrapper: ClientBootstrapper) -> None:
        self.project_path = project_path
        self.state = ClientStates.STARTING
        self.capabilities = None
        self._bootstrapper = bootstrapper
        self._bootstrapper.when_ready(lambda client: self._receive_client(client))

    def _receive_client(self, client):
        self.client = client
        self.client.send_request(
            Request.initialize(dict()),
            lambda result: self._handle_initialize_result(result))

    def _handle_initialize_result(self, result):
        self.state = ClientStates.READY
        self.capabilities = result.get('capabilities', None)

    def end(self):
        self.state = ClientStates.STOPPING
        self.client.send_request(
            Request.shutdown(),
            lambda result: self._handle_shutdown_result(result))

    def _handle_shutdown_result(self, result):
        self.client.send_notification(Notification.exit())
        self.client = None
        self.capabilities = None

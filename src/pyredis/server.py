import logging
import socket

from pyredis.config import Config

logger = logging.getLogger(__name__)

class RedisServer:
    def __init__(self, config: Config) -> None:
        self._config = config
        self._server_socket : socket.socket | None = None
    
    def start(self) -> None:
        self._server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._server_socket.bind((self._config.host, self._config.port))
        self._server_socket.listen()
        logger.info("Listening on %s:%d", self._config.host, self._config.port)
        self._accept_loop()

    def _accept_loop(self) -> None:
        assert self._server_socket is not None
        while True:
            client_socket, client_address = self._server_socket.accept()
            logger.info("Accepted connection from %s:%d", client_address[0], client_address[1])
            self._handle_client(client_socket)
    
    def _handle_client(self, client_socket: socket.socket) -> None:
        while True:
            data = client_socket.recv(1024)
            if data == b"":
                client_socket.close()
                return
            client_socket.sendall(data)
    
    def stop(self) -> None:
        if self._server_socket is not None:
            self._server_socket.close()
            logger.info("Server stopped")


def create_server(config: Config) -> RedisServer:
    return RedisServer(config)
    
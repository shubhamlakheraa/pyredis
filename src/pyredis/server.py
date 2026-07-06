import logging
import selectors
import socket
from typing import Callable, Optional

from pyredis.config import Config

logger = logging.getLogger(__name__)

Handler = Callable[[socket.socket], None]


class RedisServer:
    def __init__(self, config: Config) -> None:
        self._config = config
        self._server_socket: Optional[socket.socket] = None
        self._sel: Optional[selectors.BaseSelector] = None
        self._running: bool = False

    def start(self) -> None:
        self._sel = selectors.DefaultSelector()
        self._server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._server_socket.bind((self._config.host, self._config.port))
        self._server_socket.listen()
        self._server_socket.setblocking(False)
        self._sel.register(self._server_socket, selectors.EVENT_READ, self._on_accept)

        self._running = True
        logger.info("Listening on %s:%d", self._config.host, self._config.port)

        try:
            while self._running:
                events = self._sel.select(timeout=1.0)
                for key, _mask in events:
                    handler: Handler = key.data
                    sock: socket.socket = key.fileobj  # type: ignore[assignment]
                    try:
                        handler(sock)
                    except Exception:
                        logger.exception("handler crashed; dropping client")
                        self._drop_client(sock)
        finally:
            self._cleanup()

    def _on_accept(self, server_sock: socket.socket) -> None:
        assert self._sel is not None
        client_sock, client_addr = server_sock.accept()
        logger.info("Accepted connection from %s:%d", client_addr[0], client_addr[1])
        client_sock.setblocking(False)
        self._sel.register(client_sock, selectors.EVENT_READ, self._on_read)

    def _on_read(self, client_sock: socket.socket) -> None:
        data = client_sock.recv(1024)
        if not data:
            self._drop_client(client_sock)
            return
    # TODO T04: replace with outbound buffer + write-readiness arming.
    # sendall is fine for the echo-only T03 but breaks under real load
    # on a non-blocking socket when the kernel send buffer fills.
        client_sock.sendall(data)

    def _drop_client(self, sock: socket.socket) -> None:
        assert self._sel is not None
        try:
            self._sel.unregister(sock)
        except (KeyError, ValueError):
            pass
        try:
            sock.close()
        except OSError:
            pass

    def stop(self) -> None:
        self._running = False

    def _cleanup(self) -> None:
        if self._sel is None:
            return
        if self._server_socket is not None:
            try:
                self._sel.unregister(self._server_socket)
            except (KeyError, ValueError):
                pass
            self._server_socket.close()
            self._server_socket = None
        self._sel.close()
        self._sel = None
        logger.info("Server stopped")


def create_server(config: Config) -> RedisServer:
    return RedisServer(config)

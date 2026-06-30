import logging
import selectors
import socket
from typing import Optional

from pyredis.config import Config
from pyredis.errors import RedisError

logger = logging.getLogger(__name__)


class RedisServer:
    def __init__(self, config: Config) -> None:
        self._config = config
        self._selector: selectors.BaseSelector = selectors.DefaultSelector()
        self._server_socket: Optional[socket.socket] = None
        self._clients: dict[socket.socket, None] = {}
        self._running: bool = False

    def start(self) -> None:
        self._selector = selectors.DefaultSelector()
        self._server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._server_socket.bind((self._config.host, self._config.port))
        self._server_socket.listen()
        self._server_socket.setblocking(False)
        self._selector.register(self._server_socket, selectors.EVENT_READ)

        self._running = True
        logger.info("Listening on %s:%d", self._config.host, self._config.port)

        try:
            while self._running:
                try:
                    events = self._selector.select(timeout=1.0)
                except OSError:
                    break
                for _key, _mask in events:
                    pass
        except RedisError as exc:
            logger.error("Server error: %s", exc)
        finally:
            if self._server_socket is not None:
                self._selector.unregister(self._server_socket)
                self._server_socket.close()
                self._server_socket = None
            self._selector.close()
            logger.info("Server stopped")

    def stop(self) -> None:
        self._running = False


def create_server(config: Config) -> RedisServer:
    return RedisServer(config)

import logging
import selectors
import socket
from typing import Optional

from pyredis.config import Config
from pyredis.connection import ConnectionClosed, RedisConnection
from pyredis.encoder import encode_error, encode_simple_string
from pyredis.errors import ProtocolError, RedisError
from pyredis.resp import parse_command

logger = logging.getLogger(__name__)


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
        # data=None marks the listener; clients get a RedisConnection in data.
        self._sel.register(self._server_socket, selectors.EVENT_READ, data=None)

        self._running = True
        logger.info("Listening on %s:%d", self._config.host, self._config.port)

        try:
            while self._running:
                events = self._sel.select(timeout=1.0)
                for key, mask in events:
                    if key.data is None:
                        try:
                            self._on_accept()
                        except Exception:
                            logger.exception("accept failed")
                        continue

                    conn: RedisConnection = key.data
                    if conn.closed:
                        # Stale event from before we dropped this conn
                        # (kqueue/epoll can queue events across close).
                        continue
                    dropped = False
                    # Flush queued output first — if the peer is closing,
                    # we still want to deliver the echo before we drop.
                    if mask & selectors.EVENT_WRITE:
                        try:
                            self._on_write(conn)
                        except Exception:
                            logger.exception("write handler crashed")
                            self._drop(conn)
                            dropped = True
                    if not dropped and mask & selectors.EVENT_READ:
                        try:
                            self._on_read(conn)
                        except ConnectionClosed:
                            self._drop(conn)
                            dropped = True
                        except Exception:
                            logger.exception("read handler crashed")
                            self._drop(conn)
                            dropped = True
        finally:
            self._cleanup()

    def _on_accept(self) -> None:
        assert self._sel is not None
        assert self._server_socket is not None
        client_sock, client_addr = self._server_socket.accept()
        logger.info("Accepted connection from %s:%d", client_addr[0], client_addr[1])
        client_sock.setblocking(False)
        conn = RedisConnection(client_sock)
        self._sel.register(client_sock, selectors.EVENT_READ, data=conn)

    def _on_read(self, conn: RedisConnection) -> None:
        conn.recv_into_buffer()
        while True:
            try:
                args, n = parse_command(conn.inbound_buffer)
            except ProtocolError as e:
                conn.enqueue(encode_error(f"ERR {e}"))
                self._arm_write(conn)
                self._drop(conn)
                return
            if args is None:
                break
            conn.consume(n)
            try:
                response = self._dispatch(args)
            except RedisError as e:
                response = encode_error(str(e))
            conn.enqueue(response)
            self._arm_write(conn)

    def _dispatch(self, args: list[bytes]) -> bytes:
        # T07 will replace this with real command routing.
        return encode_simple_string("OK")

    def _on_write(self, conn: RedisConnection) -> None:
        conn.flush()
        if not conn.has_pending_output():
            self._disarm_write(conn)

    def _arm_write(self, conn: RedisConnection) -> None:
        assert self._sel is not None
        if conn.write_armed:
            return
        self._sel.modify(
            conn.socket,
            selectors.EVENT_READ | selectors.EVENT_WRITE,
            data=conn,
        )
        conn.set_write_armed(True)

    def _disarm_write(self, conn: RedisConnection) -> None:
        assert self._sel is not None
        if not conn.write_armed:
            return
        self._sel.modify(conn.socket, selectors.EVENT_READ, data=conn)
        conn.set_write_armed(False)

    def _drop(self, conn: RedisConnection) -> None:
        assert self._sel is not None
        try:
            self._sel.unregister(conn.socket)
        except (KeyError, ValueError):
            pass
        conn.close()

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

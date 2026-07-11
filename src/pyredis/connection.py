import socket

READ_CHUNK = 4096

# TODO T23: enforce a max inbound size to prevent memory-exhaustion DoS.
# Noted here as documentation; not enforced yet.
MAX_INBOUND_BUFFER = 1 << 20  # 1 MiB


class ConnectionClosed(Exception):
    """Raised when the peer closed the socket (recv returned b"")."""


class RedisConnection:
    def __init__(self, sock: socket.socket) -> None:
        self._socket = sock
        self._inbound_buffer: bytearray = bytearray()
        self._outbound_buffer: bytearray = bytearray()
        self._write_armed: bool = False
        self._closed: bool = False

    @property
    def socket(self) -> socket.socket:
        return self._socket

    @property
    def closed(self) -> bool:
        return self._closed

    @property
    def write_armed(self) -> bool:
        return self._write_armed

    def set_write_armed(self, armed: bool) -> None:
        self._write_armed = armed

    def has_pending_output(self) -> bool:
        return len(self._outbound_buffer) > 0

    def recv_into_buffer(self) -> None:
        """Read one chunk from the socket into the inbound buffer."""
        chunk = self._socket.recv(READ_CHUNK)
        if not chunk:
            raise ConnectionClosed
        self._inbound_buffer += chunk

    @property
    def inbound_buffer(self) -> bytearray:
        return self._inbound_buffer

    def consume(self, n: int) -> None:
        """Remove the first *n* bytes from the inbound buffer."""
        del self._inbound_buffer[:n]

    def enqueue(self, data: bytes) -> None:
        self._outbound_buffer += data

    def flush(self) -> None:
        """
        Send as much as the kernel will take. If the kernel send buffer
        is full, send() returns short and we keep the tail for later.
        """
        if not self._outbound_buffer:
            return
        n = self._socket.send(self._outbound_buffer)
        del self._outbound_buffer[:n]

    def close(self) -> None:
        self._closed = True
        try:
            self._socket.close()
        except OSError:
            pass

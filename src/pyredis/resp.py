from pyredis.errors import ProtocolError

_Buffer = bytes | bytearray


def parse_command(buffer: _Buffer) -> tuple[list[bytes] | None, int]:
    """
    Try to parse one complete RESP array-of-bulk-strings frame from *buffer*.

    Returns (args, bytes_consumed) on success, or (None, 0) when the buffer
    holds an incomplete frame.  Raises ProtocolError on malformed input.
    """
    if not buffer:
        return None, 0

    if buffer[0:1] != b"*":
        raise ProtocolError(f"Expected RESP array ('*'), got {buffer[0:1]!r}")

    header = _parse_array_header(buffer, 0)
    if header is None:
        return None, 0
    count, cursor = header

    if count == -1:
        return None, 0
    if count == 0:
        return [], cursor

    args: list[bytes] = []
    for _ in range(count):
        result = _parse_bulk_string(buffer, cursor)
        if result is None:
            return None, 0
        value, cursor = result
        args.append(value)

    return args, cursor


def _parse_array_header(buffer: _Buffer, cursor: int) -> tuple[int, int] | None:
    end = buffer.find(b"\r\n", cursor)
    if end == -1:
        return None
    try:
        count = int(buffer[cursor + 1 : end])
    except ValueError:
        raise ProtocolError(f"Invalid array count: {buffer[cursor + 1:end]!r}")
    if count < -1:
        raise ProtocolError(f"Invalid array count: {count}")
    return count, end + 2


def _parse_bulk_string(buffer: _Buffer, cursor: int) -> tuple[bytes, int] | None:
    if cursor >= len(buffer):
        return None

    if buffer[cursor : cursor + 1] != b"$":
        raise ProtocolError(
            f"Expected bulk string ('$'), got {buffer[cursor:cursor+1]!r}"
        )
    cursor += 1

    end = buffer.find(b"\r\n", cursor)
    if end == -1:
        return None

    try:
        length = int(buffer[cursor:end])
    except ValueError:
        raise ProtocolError(f"Invalid bulk string length: {buffer[cursor:end]!r}")

    cursor = end + 2

    if cursor + length + 2 > len(buffer):
        return None

    value = bytes(buffer[cursor : cursor + length])
    cursor += length

    if buffer[cursor : cursor + 2] != b"\r\n":
        raise ProtocolError("Missing CRLF after bulk string data")

    cursor += 2
    return value, cursor

from __future__ import annotations

RespValue = bytes | None | int | list["RespValue"]


def encode_simple_string(s: str) -> bytes:
    return f"+{s}\r\n".encode()


def encode_error(msg: str) -> bytes:
    return f"-{msg}\r\n".encode()


def encode_integer(n: int) -> bytes:
    return f":{n}\r\n".encode()


def encode_bulk(data: bytes | None) -> bytes:
    if data is None:
        return b"$-1\r\n"
    return f"${len(data)}\r\n".encode() + data + b"\r\n"


def encode_array(items: list[RespValue]) -> bytes:
    result = f"*{len(items)}\r\n".encode()
    for item in items:
        if isinstance(item, list):
            result += encode_array(item)
        elif isinstance(item, int):
            result += encode_integer(item)
        else:
            result += encode_bulk(item)
    return result

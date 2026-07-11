from pyredis.encoder import (
    encode_array,
    encode_bulk,
    encode_error,
    encode_integer,
    encode_simple_string,
)
from pyredis.resp import parse_command


# ---------------------------------------------------------------------------
# encode_simple_string
# ---------------------------------------------------------------------------


def test_simple_string_ok() -> None:
    assert encode_simple_string("OK") == b"+OK\r\n"


def test_simple_string_pong() -> None:
    assert encode_simple_string("PONG") == b"+PONG\r\n"


# ---------------------------------------------------------------------------
# encode_error
# ---------------------------------------------------------------------------


def test_error_generic() -> None:
    assert encode_error("ERR unknown command") == b"-ERR unknown command\r\n"


def test_error_wrongtype() -> None:
    assert encode_error("WRONGTYPE Operation against a key holding the wrong kind of value") == (
        b"-WRONGTYPE Operation against a key holding the wrong kind of value\r\n"
    )


# ---------------------------------------------------------------------------
# encode_integer
# ---------------------------------------------------------------------------


def test_integer_positive() -> None:
    assert encode_integer(4) == b":4\r\n"


def test_integer_zero() -> None:
    assert encode_integer(0) == b":0\r\n"


def test_integer_negative() -> None:
    assert encode_integer(-1) == b":-1\r\n"


def test_integer_large() -> None:
    assert encode_integer(1_000_000) == b":1000000\r\n"


# ---------------------------------------------------------------------------
# encode_bulk
# ---------------------------------------------------------------------------


def test_bulk_normal() -> None:
    assert encode_bulk(b"bar") == b"$3\r\nbar\r\n"


def test_bulk_empty_string() -> None:
    assert encode_bulk(b"") == b"$0\r\n\r\n"


def test_bulk_null() -> None:
    assert encode_bulk(None) == b"$-1\r\n"


def test_bulk_binary_safe() -> None:
    data = b"ab\r\ncd"
    assert encode_bulk(data) == b"$6\r\nab\r\ncd\r\n"


def test_bulk_length_is_byte_count() -> None:
    data = "café".encode()  # 5 bytes in UTF-8
    result = encode_bulk(data)
    assert result.startswith(b"$5\r\n")


# ---------------------------------------------------------------------------
# encode_array
# ---------------------------------------------------------------------------


def test_array_two_elements() -> None:
    assert encode_array([b"a", b"b"]) == b"*2\r\n$1\r\na\r\n$1\r\nb\r\n"


def test_array_empty() -> None:
    assert encode_array([]) == b"*0\r\n"


def test_array_with_null_element() -> None:
    result = encode_array([b"foo", None, b"bar"])
    assert result == b"*3\r\n$3\r\nfoo\r\n$-1\r\n$3\r\nbar\r\n"


def test_array_with_integer_element() -> None:
    result = encode_array([b"count", 42])
    assert result == b"*2\r\n$5\r\ncount\r\n:42\r\n"


def test_array_nested() -> None:
    inner = [b"a", b"b"]
    outer = encode_array([inner, b"c"])
    assert outer == b"*2\r\n*2\r\n$1\r\na\r\n$1\r\nb\r\n$1\r\nc\r\n"


def test_array_round_trips_through_resp_parser() -> None:
    # encode an array of bulk strings, then decode it with the T05 parser
    encoded = encode_array([b"SET", b"foo", b"bar"])
    args, n = parse_command(encoded)
    assert args == [b"SET", b"foo", b"bar"]
    assert n == len(encoded)

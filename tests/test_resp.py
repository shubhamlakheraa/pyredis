import pytest

from pyredis.errors import ProtocolError
from pyredis.resp import parse_command


# ---------------------------------------------------------------------------
# Happy-path: complete frames
# ---------------------------------------------------------------------------


def test_single_bulk_string_command() -> None:
    args, n = parse_command(b"*1\r\n$4\r\nPING\r\n")
    assert args == [b"PING"]
    assert n == 14


def test_two_arg_command() -> None:
    args, n = parse_command(b"*2\r\n$4\r\nPING\r\n$5\r\nhello\r\n")
    assert args == [b"PING", b"hello"]
    assert n == 25


def test_three_arg_command() -> None:
    args, n = parse_command(b"*3\r\n$3\r\nSET\r\n$3\r\nfoo\r\n$3\r\nbar\r\n")
    assert args == [b"SET", b"foo", b"bar"]
    assert n == 31


def test_bytes_consumed_exact() -> None:
    frame = b"*1\r\n$4\r\nPING\r\n"
    args, n = parse_command(frame)
    assert n == len(frame)


def test_value_with_spaces() -> None:
    args, n = parse_command(b"*2\r\n$3\r\nSET\r\n$7\r\nhel lo \r\n")
    assert args == [b"SET", b"hel lo "]


def test_binary_safe_value() -> None:
    # value contains \r\n bytes — length-prefix must handle it, not delimiter scan
    payload = b"ab\r\ncd"
    frame = b"*1\r\n$6\r\n" + payload + b"\r\n"
    args, n = parse_command(frame)
    assert args == [payload]
    assert n == len(frame)


def test_empty_bulk_string() -> None:
    args, n = parse_command(b"*1\r\n$0\r\n\r\n")
    assert args == [b""]
    assert n == 10


# ---------------------------------------------------------------------------
# Special array counts
# ---------------------------------------------------------------------------


def test_empty_array() -> None:
    args, n = parse_command(b"*0\r\n")
    assert args == []
    assert n == 4


def test_null_array_returns_none() -> None:
    args, n = parse_command(b"*-1\r\n")
    assert args is None
    assert n == 0


# ---------------------------------------------------------------------------
# Incomplete frames — must return (None, 0) and not mutate the buffer
# ---------------------------------------------------------------------------


def test_empty_buffer_is_incomplete() -> None:
    assert parse_command(b"") == (None, 0)


def test_only_star_is_incomplete() -> None:
    assert parse_command(b"*") == (None, 0)


def test_array_header_no_crlf_is_incomplete() -> None:
    assert parse_command(b"*2") == (None, 0)


def test_partial_bulk_string_header_is_incomplete() -> None:
    # array header complete, but bulk string header truncated
    assert parse_command(b"*1\r\n$4") == (None, 0)


def test_partial_bulk_string_data_is_incomplete() -> None:
    # length says 4 bytes but only 2 present
    assert parse_command(b"*1\r\n$4\r\nPI") == (None, 0)


def test_missing_trailing_crlf_on_data_is_incomplete() -> None:
    # all 4 bytes present but no trailing \r\n
    assert parse_command(b"*1\r\n$4\r\nPING") == (None, 0)


def test_incomplete_second_argument() -> None:
    # first arg complete, second truncated
    assert parse_command(b"*2\r\n$4\r\nPING\r\n$5\r\nhel") == (None, 0)


def test_incomplete_returns_zero_consumed() -> None:
    _, n = parse_command(b"*2\r\n$4\r\nPING\r\n$5\r\nhel")
    assert n == 0


# ---------------------------------------------------------------------------
# Malformed input — must raise ProtocolError
# ---------------------------------------------------------------------------


def test_inline_command_raises() -> None:
    with pytest.raises(ProtocolError):
        parse_command(b"PING\r\n")


def test_non_integer_array_count_raises() -> None:
    with pytest.raises(ProtocolError):
        parse_command(b"*abc\r\n")


def test_count_below_minus_one_raises() -> None:
    with pytest.raises(ProtocolError):
        parse_command(b"*-2\r\n")


def test_non_integer_bulk_length_raises() -> None:
    with pytest.raises(ProtocolError):
        parse_command(b"*1\r\n$abc\r\nhello\r\n")


def test_wrong_sigil_for_bulk_string_raises() -> None:
    # : is the sigil for simple strings, not bulk strings
    with pytest.raises(ProtocolError):
        parse_command(b"*1\r\n:4\r\nPING\r\n")


def test_missing_crlf_after_data_raises() -> None:
    # 4 bytes present but followed by XX instead of \r\n
    with pytest.raises(ProtocolError):
        parse_command(b"*1\r\n$4\r\nPINGXX")


# ---------------------------------------------------------------------------
# Pipelining — multiple frames back-to-back in the same buffer
# ---------------------------------------------------------------------------


def test_two_pipelined_frames() -> None:
    buf = b"*1\r\n$4\r\nPING\r\n*3\r\n$3\r\nSET\r\n$3\r\nfoo\r\n$3\r\nbar\r\n"
    args1, n1 = parse_command(buf)
    assert args1 == [b"PING"]
    args2, n2 = parse_command(buf[n1:])
    assert args2 == [b"SET", b"foo", b"bar"]
    assert n1 + n2 == len(buf)


def test_pipelined_frame_with_trailing_incomplete() -> None:
    complete = b"*1\r\n$4\r\nPING\r\n"
    partial = b"*2\r\n$3\r\nGET"
    buf = complete + partial
    args, n = parse_command(buf)
    assert args == [b"PING"]
    assert n == len(complete)
    # second parse on remainder should be incomplete
    assert parse_command(buf[n:]) == (None, 0)


# ---------------------------------------------------------------------------
# bytearray input (connection.py hands us a bytearray)
# ---------------------------------------------------------------------------


def test_accepts_bytearray() -> None:
    buf = bytearray(b"*1\r\n$4\r\nPING\r\n")
    args, n = parse_command(buf)
    assert args == [b"PING"]
    assert n == 14

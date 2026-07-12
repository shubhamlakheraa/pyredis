import pytest

from pyredis.commands import create_command_table, CommandEntry
from pyredis.store import KeyValueStore

TABLE = create_command_table(KeyValueStore())


def dispatch(args: list[bytes]) -> bytes:
    """Minimal dispatcher that mirrors server._dispatch logic."""
    cmd = args[0].upper()
    entry: CommandEntry | None = TABLE.get(cmd)
    if entry is None:
        from pyredis.encoder import encode_error
        return encode_error(f"ERR unknown command '{cmd.decode()}'")
    n = len(args)
    if n < entry.arity_min or (entry.arity_max != -1 and n > entry.arity_max):
        from pyredis.encoder import encode_error
        return encode_error(f"ERR wrong number of arguments for '{cmd.decode()}' command")
    return entry.handler(args)


# ---------------------------------------------------------------------------
# PING
# ---------------------------------------------------------------------------


def test_ping_no_args() -> None:
    assert dispatch([b"PING"]) == b"+PONG\r\n"


def test_ping_with_message() -> None:
    assert dispatch([b"PING", b"hello"]) == b"$5\r\nhello\r\n"


def test_ping_case_insensitive_lower() -> None:
    assert dispatch([b"ping"]) == b"+PONG\r\n"


def test_ping_case_insensitive_mixed() -> None:
    assert dispatch([b"Ping"]) == b"+PONG\r\n"


# ---------------------------------------------------------------------------
# ECHO
# ---------------------------------------------------------------------------


def test_echo_returns_bulk_string() -> None:
    assert dispatch([b"ECHO", b"world"]) == b"$5\r\nworld\r\n"


def test_echo_empty_string() -> None:
    assert dispatch([b"ECHO", b""]) == b"$0\r\n\r\n"


def test_echo_binary_safe() -> None:
    payload = b"ab\r\ncd"
    assert dispatch([b"ECHO", payload]) == b"$6\r\nab\r\ncd\r\n"


# ---------------------------------------------------------------------------
# Unknown command
# ---------------------------------------------------------------------------


def test_unknown_command_returns_err() -> None:
    result = dispatch([b"FOOBAR"])
    assert result.startswith(b"-ERR")


def test_unknown_command_contains_name() -> None:
    result = dispatch([b"FOOBAR"])
    assert b"FOOBAR" in result or b"foobar" in result.lower()


# ---------------------------------------------------------------------------
# Wrong arity
# ---------------------------------------------------------------------------


def test_echo_no_args_wrong_arity() -> None:
    result = dispatch([b"ECHO"])
    assert result.startswith(b"-ERR")


def test_echo_too_many_args_wrong_arity() -> None:
    result = dispatch([b"ECHO", b"a", b"b"])
    assert result.startswith(b"-ERR")


def test_ping_too_many_args_wrong_arity() -> None:
    result = dispatch([b"PING", b"a", b"b"])
    assert result.startswith(b"-ERR")


# ---------------------------------------------------------------------------
# Adding a new command is a two-line change
# ---------------------------------------------------------------------------


def test_command_table_is_extensible() -> None:
    from pyredis.encoder import encode_simple_string
    from pyredis.commands import CommandEntry

    def handle_hello(args: list[bytes]) -> bytes:
        return encode_simple_string("OK")

    table = create_command_table(KeyValueStore())
    table[b"HELLO"] = CommandEntry(handle_hello, 1, 1, frozenset({"fast"}), 0, 0)
    assert b"HELLO" in table

from collections import deque

import pytest

from pyredis.commands.lists import (
    make_llen,
    make_lpop,
    make_lpush,
    make_lrange,
    make_rpop,
    make_rpush,
)
from pyredis.commands.strings import make_exists, make_set
from pyredis.errors import WrongTypeError
from pyredis.object import RedisObject
from pyredis.store import KeyValueStore


def make_store() -> KeyValueStore:
    return KeyValueStore()


# ---------------------------------------------------------------------------
# RPUSH / LPUSH basics
# ---------------------------------------------------------------------------


def test_rpush_returns_new_length() -> None:
    store = make_store()
    assert make_rpush(store)([b"RPUSH", b"l", b"a", b"b", b"c"]) == b":3\r\n"


def test_rpush_preserves_input_order() -> None:
    store = make_store()
    make_rpush(store)([b"RPUSH", b"l", b"a", b"b", b"c"])
    assert make_lrange(store)([b"LRANGE", b"l", b"0", b"-1"]) == (
        b"*3\r\n$1\r\na\r\n$1\r\nb\r\n$1\r\nc\r\n"
    )


def test_lpush_reverses_input_order() -> None:
    store = make_store()
    make_lpush(store)([b"LPUSH", b"l", b"a", b"b", b"c"])
    # each value is prepended one-at-a-time, so 'c' ends up first
    assert make_lrange(store)([b"LRANGE", b"l", b"0", b"-1"]) == (
        b"*3\r\n$1\r\nc\r\n$1\r\nb\r\n$1\r\na\r\n"
    )


def test_rpush_then_rpush_appends() -> None:
    store = make_store()
    make_rpush(store)([b"RPUSH", b"l", b"a"])
    assert make_rpush(store)([b"RPUSH", b"l", b"b"]) == b":2\r\n"


# ---------------------------------------------------------------------------
# LPOP / RPOP
# ---------------------------------------------------------------------------


def test_lpop_returns_head() -> None:
    store = make_store()
    make_rpush(store)([b"RPUSH", b"l", b"a", b"b", b"c"])
    assert make_lpop(store)([b"LPOP", b"l"]) == b"$1\r\na\r\n"
    assert make_llen(store)([b"LLEN", b"l"]) == b":2\r\n"


def test_rpop_returns_tail() -> None:
    store = make_store()
    make_rpush(store)([b"RPUSH", b"l", b"a", b"b", b"c"])
    assert make_rpop(store)([b"RPOP", b"l"]) == b"$1\r\nc\r\n"


def test_lpop_on_missing_key_returns_null_bulk() -> None:
    store = make_store()
    assert make_lpop(store)([b"LPOP", b"missing"]) == b"$-1\r\n"


def test_rpop_on_missing_key_returns_null_bulk() -> None:
    store = make_store()
    assert make_rpop(store)([b"RPOP", b"missing"]) == b"$-1\r\n"


def test_popping_last_element_deletes_key() -> None:
    store = make_store()
    make_rpush(store)([b"RPUSH", b"l", b"only"])
    make_lpop(store)([b"LPOP", b"l"])
    assert make_exists(store)([b"EXISTS", b"l"]) == b":0\r\n"


# ---------------------------------------------------------------------------
# LLEN
# ---------------------------------------------------------------------------


def test_llen_missing_key_returns_0() -> None:
    store = make_store()
    assert make_llen(store)([b"LLEN", b"missing"]) == b":0\r\n"


def test_llen_after_pushes() -> None:
    store = make_store()
    make_rpush(store)([b"RPUSH", b"l", b"a", b"b", b"c", b"d"])
    assert make_llen(store)([b"LLEN", b"l"]) == b":4\r\n"


# ---------------------------------------------------------------------------
# LRANGE — clamping and negative indices
# ---------------------------------------------------------------------------


def test_lrange_full_with_negative_stop() -> None:
    store = make_store()
    make_rpush(store)([b"RPUSH", b"l", b"a", b"b", b"c"])
    assert make_lrange(store)([b"LRANGE", b"l", b"0", b"-1"]) == (
        b"*3\r\n$1\r\na\r\n$1\r\nb\r\n$1\r\nc\r\n"
    )


def test_lrange_negative_start_gets_tail() -> None:
    store = make_store()
    make_rpush(store)([b"RPUSH", b"l", b"a", b"b", b"c"])
    assert make_lrange(store)([b"LRANGE", b"l", b"-2", b"-1"]) == (
        b"*2\r\n$1\r\nb\r\n$1\r\nc\r\n"
    )


def test_lrange_start_past_end_returns_empty() -> None:
    store = make_store()
    make_rpush(store)([b"RPUSH", b"l", b"a", b"b", b"c"])
    assert make_lrange(store)([b"LRANGE", b"l", b"500", b"1000"]) == b"*0\r\n"


def test_lrange_stop_beyond_length_clamps() -> None:
    store = make_store()
    make_rpush(store)([b"RPUSH", b"l", b"a", b"b", b"c"])
    assert make_lrange(store)([b"LRANGE", b"l", b"0", b"100"]) == (
        b"*3\r\n$1\r\na\r\n$1\r\nb\r\n$1\r\nc\r\n"
    )


def test_lrange_start_greater_than_stop_returns_empty() -> None:
    store = make_store()
    make_rpush(store)([b"RPUSH", b"l", b"a", b"b", b"c"])
    assert make_lrange(store)([b"LRANGE", b"l", b"5", b"2"]) == b"*0\r\n"


def test_lrange_very_negative_indices_return_empty() -> None:
    store = make_store()
    make_rpush(store)([b"RPUSH", b"l", b"a", b"b", b"c"])
    # start=-500 → clamped to 0; stop=-400 → -397 → clamped to -1 → start > stop
    assert make_lrange(store)([b"LRANGE", b"l", b"-500", b"-400"]) == b"*0\r\n"


def test_lrange_missing_key_returns_empty_array() -> None:
    store = make_store()
    assert make_lrange(store)([b"LRANGE", b"missing", b"0", b"-1"]) == b"*0\r\n"


# ---------------------------------------------------------------------------
# Type discipline
# ---------------------------------------------------------------------------


def test_lpush_on_string_key_raises_wrongtype() -> None:
    store = make_store()
    make_set(store)([b"SET", b"foo", b"bar"])
    with pytest.raises(WrongTypeError):
        make_lpush(store)([b"LPUSH", b"foo", b"x"])


def test_llen_on_string_key_raises_wrongtype() -> None:
    store = make_store()
    make_set(store)([b"SET", b"foo", b"bar"])
    with pytest.raises(WrongTypeError):
        make_llen(store)([b"LLEN", b"foo"])


def test_rpop_on_string_key_raises_wrongtype() -> None:
    store = make_store()
    make_set(store)([b"SET", b"foo", b"bar"])
    with pytest.raises(WrongTypeError):
        make_rpop(store)([b"RPOP", b"foo"])


# ---------------------------------------------------------------------------
# Encoding transitions (used later by OBJECT ENCODING in T23)
# ---------------------------------------------------------------------------


def test_small_list_encoding_is_listpack() -> None:
    store = make_store()
    make_rpush(store)([b"RPUSH", b"l"] + [b"x"] * 10)
    obj = store.get_object(b"l")
    assert obj is not None
    assert obj.encoding == "listpack"


def test_large_list_encoding_flips_to_quicklist() -> None:
    store = make_store()
    make_rpush(store)([b"RPUSH", b"l"] + [b"x"] * 200)
    obj = store.get_object(b"l")
    assert obj is not None
    assert obj.encoding == "quicklist"


# ---------------------------------------------------------------------------
# LRANGE parse error on non-integer bounds
# ---------------------------------------------------------------------------


def test_lrange_non_integer_start_raises() -> None:
    from pyredis.errors import CommandError

    store = make_store()
    make_rpush(store)([b"RPUSH", b"l", b"a"])
    with pytest.raises(CommandError):
        make_lrange(store)([b"LRANGE", b"l", b"notanint", b"0"])

import pytest

from pyredis.commands.strings import (
    make_decr,
    make_decrby,
    make_del,
    make_exists,
    make_get,
    make_incr,
    make_incrby,
    make_set,
    make_type,
)
from pyredis.commands.lists import make_lpush
from pyredis.errors import CommandError, WrongTypeError
from pyredis.store import KeyValueStore


def make_store() -> KeyValueStore:
    return KeyValueStore()


# ---------------------------------------------------------------------------
# SET
# ---------------------------------------------------------------------------


def test_set_returns_ok() -> None:
    store = make_store()
    assert make_set(store)([b"SET", b"foo", b"bar"]) == b"+OK\r\n"


def test_set_overwrites_existing_key() -> None:
    store = make_store()
    handle_set = make_set(store)
    handle_set([b"SET", b"foo", b"first"])
    handle_set([b"SET", b"foo", b"second"])
    obj = store.get_object(b"foo")
    assert obj is not None
    assert obj.value == b"second"


# ---------------------------------------------------------------------------
# GET
# ---------------------------------------------------------------------------


def test_get_missing_key_returns_null_bulk() -> None:
    store = make_store()
    assert make_get(store)([b"GET", b"missing"]) == b"$-1\r\n"


def test_get_existing_key_returns_value() -> None:
    store = make_store()
    make_set(store)([b"SET", b"foo", b"bar"])
    assert make_get(store)([b"GET", b"foo"]) == b"$3\r\nbar\r\n"


def test_get_after_del_returns_null_bulk() -> None:
    store = make_store()
    make_set(store)([b"SET", b"foo", b"bar"])
    make_del(store)([b"DEL", b"foo"])
    assert make_get(store)([b"GET", b"foo"]) == b"$-1\r\n"


# ---------------------------------------------------------------------------
# DEL
# ---------------------------------------------------------------------------


def test_del_existing_key_returns_1() -> None:
    store = make_store()
    make_set(store)([b"SET", b"foo", b"bar"])
    assert make_del(store)([b"DEL", b"foo"]) == b":1\r\n"


def test_del_missing_key_returns_0() -> None:
    store = make_store()
    assert make_del(store)([b"DEL", b"missing"]) == b":0\r\n"


def test_del_multiple_keys_returns_count() -> None:
    store = make_store()
    make_set(store)([b"SET", b"a", b"1"])
    make_set(store)([b"SET", b"b", b"2"])
    assert make_del(store)([b"DEL", b"a", b"b", b"missing"]) == b":2\r\n"


# ---------------------------------------------------------------------------
# EXISTS
# ---------------------------------------------------------------------------


def test_exists_missing_returns_0() -> None:
    store = make_store()
    assert make_exists(store)([b"EXISTS", b"missing"]) == b":0\r\n"


def test_exists_present_returns_1() -> None:
    store = make_store()
    make_set(store)([b"SET", b"foo", b"bar"])
    assert make_exists(store)([b"EXISTS", b"foo"]) == b":1\r\n"


def test_exists_duplicate_keys_counts_twice() -> None:
    store = make_store()
    make_set(store)([b"SET", b"foo", b"bar"])
    assert make_exists(store)([b"EXISTS", b"foo", b"foo"]) == b":2\r\n"


# ---------------------------------------------------------------------------
# TYPE
# ---------------------------------------------------------------------------


def test_type_missing_key_returns_none() -> None:
    store = make_store()
    assert make_type(store)([b"TYPE", b"missing"]) == b"+none\r\n"


def test_type_string_key_returns_string() -> None:
    store = make_store()
    make_set(store)([b"SET", b"foo", b"bar"])
    assert make_type(store)([b"TYPE", b"foo"]) == b"+string\r\n"


# ---------------------------------------------------------------------------
# LPUSH stub raises WrongTypeError on string key
# ---------------------------------------------------------------------------


def test_lpush_on_string_key_raises_wrongtype() -> None:
    store = make_store()
    make_set(store)([b"SET", b"foo", b"bar"])
    with pytest.raises(WrongTypeError):
        make_lpush(store)([b"LPUSH", b"foo", b"x"])


# ---------------------------------------------------------------------------
# INCR
# ---------------------------------------------------------------------------


def test_incr_missing_key_starts_at_1() -> None:
    store = make_store()
    assert make_incr(store)([b"INCR", b"k"]) == b":1\r\n"


def test_incr_ten_times_returns_10() -> None:
    store = make_store()
    handle = make_incr(store)
    for _ in range(10):
        handle([b"INCR", b"k"])
    assert handle([b"INCR", b"k"]) == b":11\r\n"


def test_incr_on_non_integer_raises_error() -> None:
    store = make_store()
    make_set(store)([b"SET", b"k", b"abc"])
    with pytest.raises(CommandError, match="ERR"):
        make_incr(store)([b"INCR", b"k"])


def test_incr_result_stored_as_string() -> None:
    store = make_store()
    make_incr(store)([b"INCR", b"k"])
    assert make_get(store)([b"GET", b"k"]) == b"$1\r\n1\r\n"


def test_incr_overflow_raises_error() -> None:
    store = make_store()
    make_set(store)([b"SET", b"k", b"9223372036854775807"])
    with pytest.raises(CommandError, match="overflow"):
        make_incr(store)([b"INCR", b"k"])


def test_incr_on_wrong_type_raises_wrongtype() -> None:
    store = make_store()
    from pyredis.object import RedisObject
    store.put(b"k", RedisObject(type="list", value=[]))
    with pytest.raises(WrongTypeError):
        make_incr(store)([b"INCR", b"k"])


# ---------------------------------------------------------------------------
# DECR
# ---------------------------------------------------------------------------


def test_decr_missing_key_starts_at_minus_1() -> None:
    store = make_store()
    assert make_decr(store)([b"DECR", b"k"]) == b":-1\r\n"


def test_decr_underflow_raises_error() -> None:
    store = make_store()
    make_set(store)([b"SET", b"k", b"-9223372036854775808"])
    with pytest.raises(CommandError, match="overflow"):
        make_decr(store)([b"DECR", b"k"])


# ---------------------------------------------------------------------------
# INCRBY / DECRBY
# ---------------------------------------------------------------------------


def test_incrby_adds_delta() -> None:
    store = make_store()
    handle_incr = make_incr(store)
    handle_incrby = make_incrby(store)
    for _ in range(10):
        handle_incr([b"INCR", b"k"])
    assert handle_incrby([b"INCRBY", b"k", b"5"]) == b":15\r\n"


def test_decrby_subtracts_delta() -> None:
    store = make_store()
    make_incrby(store)([b"INCRBY", b"k", b"15"])
    assert make_decrby(store)([b"DECRBY", b"k", b"4"]) == b":11\r\n"


def test_incrby_non_integer_delta_raises_error() -> None:
    store = make_store()
    with pytest.raises(CommandError, match="ERR"):
        make_incrby(store)([b"INCRBY", b"k", b"notanumber"])


def test_decrby_non_integer_delta_raises_error() -> None:
    store = make_store()
    with pytest.raises(CommandError, match="ERR"):
        make_decrby(store)([b"DECRBY", b"k", b"notanumber"])


def test_type_after_incr_is_string() -> None:
    store = make_store()
    make_incr(store)([b"INCR", b"k"])
    assert make_type(store)([b"TYPE", b"k"]) == b"+string\r\n"

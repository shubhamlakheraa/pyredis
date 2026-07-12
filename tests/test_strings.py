import pytest

from pyredis.commands.strings import make_del, make_exists, make_get, make_set, make_type
from pyredis.commands.lists import make_lpush
from pyredis.errors import WrongTypeError
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

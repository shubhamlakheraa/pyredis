import pytest

from pyredis.errors import WrongTypeError
from pyredis.object import RedisObject
from pyredis.store import KeyValueStore


def make_store() -> KeyValueStore:
    return KeyValueStore()


def string_obj(value: bytes) -> RedisObject:
    return RedisObject(type="string", value=value)


def list_obj() -> RedisObject:
    return RedisObject(type="list", value=[])


# ---------------------------------------------------------------------------
# get_object
# ---------------------------------------------------------------------------


def test_get_missing_key_returns_none() -> None:
    store = make_store()
    assert store.get_object(b"missing") is None


def test_get_existing_key_returns_object() -> None:
    store = make_store()
    store.put(b"foo", string_obj(b"bar"))
    obj = store.get_object(b"foo")
    assert obj is not None
    assert obj.value == b"bar"


# ---------------------------------------------------------------------------
# put / overwrite
# ---------------------------------------------------------------------------


def test_put_overwrites_existing_key() -> None:
    store = make_store()
    store.put(b"foo", string_obj(b"first"))
    store.put(b"foo", string_obj(b"second"))
    obj = store.get_object(b"foo")
    assert obj is not None
    assert obj.value == b"second"


# ---------------------------------------------------------------------------
# get_or_raise
# ---------------------------------------------------------------------------


def test_get_or_raise_returns_none_for_missing_key() -> None:
    store = make_store()
    assert store.get_or_raise(b"missing", "string") is None


def test_get_or_raise_returns_object_for_correct_type() -> None:
    store = make_store()
    store.put(b"foo", string_obj(b"bar"))
    obj = store.get_or_raise(b"foo", "string")
    assert obj is not None
    assert obj.value == b"bar"


def test_get_or_raise_raises_wrongtype_on_mismatch() -> None:
    store = make_store()
    store.put(b"foo", string_obj(b"bar"))
    with pytest.raises(WrongTypeError):
        store.get_or_raise(b"foo", "list")


def test_wrongtype_error_message_has_wrongtype_prefix() -> None:
    store = make_store()
    store.put(b"foo", string_obj(b"bar"))
    with pytest.raises(WrongTypeError, match="WRONGTYPE"):
        store.get_or_raise(b"foo", "list")


# ---------------------------------------------------------------------------
# delete
# ---------------------------------------------------------------------------


def test_delete_existing_key_returns_1() -> None:
    store = make_store()
    store.put(b"foo", string_obj(b"bar"))
    assert store.delete(b"foo") == 1


def test_delete_missing_key_returns_0() -> None:
    store = make_store()
    assert store.delete(b"missing") == 0


def test_delete_multiple_keys_returns_count_removed() -> None:
    store = make_store()
    store.put(b"a", string_obj(b"1"))
    store.put(b"b", string_obj(b"2"))
    assert store.delete(b"a", b"b", b"missing") == 2


def test_deleted_key_is_gone() -> None:
    store = make_store()
    store.put(b"foo", string_obj(b"bar"))
    store.delete(b"foo")
    assert store.get_object(b"foo") is None


# ---------------------------------------------------------------------------
# exists
# ---------------------------------------------------------------------------


def test_exists_missing_key_returns_0() -> None:
    store = make_store()
    assert store.exists(b"missing") == 0


def test_exists_present_key_returns_1() -> None:
    store = make_store()
    store.put(b"foo", string_obj(b"bar"))
    assert store.exists(b"foo") == 1


def test_exists_counts_duplicate_keys() -> None:
    store = make_store()
    store.put(b"foo", string_obj(b"bar"))
    assert store.exists(b"foo", b"foo") == 2


def test_exists_mixed_present_and_missing() -> None:
    store = make_store()
    store.put(b"a", string_obj(b"1"))
    assert store.exists(b"a", b"b", b"a") == 2

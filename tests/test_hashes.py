import pytest

from pyredis.commands.hashes import (
    make_hdel,
    make_hexists,
    make_hget,
    make_hgetall,
    make_hlen,
    make_hset,
)
from pyredis.commands.lists import make_rpush
from pyredis.commands.strings import make_exists, make_set
from pyredis.errors import CommandError, WrongTypeError
from pyredis.store import KeyValueStore


def make_store() -> KeyValueStore:
    return KeyValueStore()


def parse_hgetall_reply(reply: bytes) -> dict[bytes, bytes]:
    """Parse a flat RESP array [f1, v1, f2, v2, ...] into a dict for
    order-independent comparison — HGETALL makes no ordering promise."""
    assert reply[:1] == b"*"
    header_end = reply.index(b"\r\n")
    count = int(reply[1:header_end])
    cursor = header_end + 2
    items: list[bytes] = []
    for _ in range(count):
        assert reply[cursor:cursor + 1] == b"$"
        len_end = reply.index(b"\r\n", cursor)
        length = int(reply[cursor + 1:len_end])
        cursor = len_end + 2
        items.append(reply[cursor:cursor + length])
        cursor += length + 2
    assert len(items) % 2 == 0
    return {items[i]: items[i + 1] for i in range(0, len(items), 2)}


# ---------------------------------------------------------------------------
# HSET
# ---------------------------------------------------------------------------


def test_hset_new_field_returns_1() -> None:
    store = make_store()
    assert make_hset(store)([b"HSET", b"u", b"name", b"alice"]) == b":1\r\n"


def test_hset_existing_field_returns_0() -> None:
    store = make_store()
    make_hset(store)([b"HSET", b"u", b"name", b"alice"])
    assert make_hset(store)([b"HSET", b"u", b"name", b"bob"]) == b":0\r\n"


def test_hset_multiple_new_fields_returns_count() -> None:
    store = make_store()
    result = make_hset(store)([b"HSET", b"u", b"a", b"1", b"b", b"2", b"c", b"3"])
    assert result == b":3\r\n"


def test_hset_mix_new_and_existing_returns_only_new_count() -> None:
    store = make_store()
    make_hset(store)([b"HSET", b"u", b"a", b"1"])
    result = make_hset(store)([b"HSET", b"u", b"a", b"9", b"b", b"2", b"c", b"3"])
    assert result == b":2\r\n"


def test_hset_odd_field_value_args_raises() -> None:
    store = make_store()
    with pytest.raises(CommandError):
        make_hset(store)([b"HSET", b"u", b"a", b"1", b"orphan"])


def test_hset_then_hget_returns_value() -> None:
    store = make_store()
    make_hset(store)([b"HSET", b"u", b"name", b"alice"])
    assert make_hget(store)([b"HGET", b"u", b"name"]) == b"$5\r\nalice\r\n"


# ---------------------------------------------------------------------------
# HGET
# ---------------------------------------------------------------------------


def test_hget_missing_key_returns_null_bulk() -> None:
    store = make_store()
    assert make_hget(store)([b"HGET", b"missing", b"f"]) == b"$-1\r\n"


def test_hget_missing_field_returns_null_bulk() -> None:
    store = make_store()
    make_hset(store)([b"HSET", b"u", b"name", b"alice"])
    assert make_hget(store)([b"HGET", b"u", b"missing"]) == b"$-1\r\n"


# ---------------------------------------------------------------------------
# HDEL and empty-after-delete
# ---------------------------------------------------------------------------


def test_hdel_removes_field_returns_1() -> None:
    store = make_store()
    make_hset(store)([b"HSET", b"u", b"name", b"alice"])
    assert make_hdel(store)([b"HDEL", b"u", b"name"]) == b":1\r\n"


def test_hdel_missing_field_returns_0() -> None:
    store = make_store()
    make_hset(store)([b"HSET", b"u", b"name", b"alice"])
    assert make_hdel(store)([b"HDEL", b"u", b"missing"]) == b":0\r\n"


def test_hdel_multiple_fields_counts_only_removed() -> None:
    store = make_store()
    make_hset(store)([b"HSET", b"u", b"a", b"1", b"b", b"2"])
    assert make_hdel(store)([b"HDEL", b"u", b"a", b"b", b"missing"]) == b":2\r\n"


def test_hdel_missing_key_returns_0() -> None:
    store = make_store()
    assert make_hdel(store)([b"HDEL", b"missing", b"f"]) == b":0\r\n"


def test_hdel_last_field_deletes_key() -> None:
    store = make_store()
    make_hset(store)([b"HSET", b"u", b"only", b"v"])
    make_hdel(store)([b"HDEL", b"u", b"only"])
    assert make_exists(store)([b"EXISTS", b"u"]) == b":0\r\n"


# ---------------------------------------------------------------------------
# HGETALL
# ---------------------------------------------------------------------------


def test_hgetall_missing_key_returns_empty_array() -> None:
    store = make_store()
    assert make_hgetall(store)([b"HGETALL", b"missing"]) == b"*0\r\n"


def test_hgetall_returns_all_fields_and_values() -> None:
    store = make_store()
    make_hset(store)([b"HSET", b"u", b"name", b"alice", b"age", b"26"])
    reply = make_hgetall(store)([b"HGETALL", b"u"])
    parsed = parse_hgetall_reply(reply)
    assert parsed == {b"name": b"alice", b"age": b"26"}


def test_hgetall_after_hdel_reflects_removal() -> None:
    store = make_store()
    make_hset(store)([b"HSET", b"u", b"a", b"1", b"b", b"2", b"c", b"3"])
    make_hdel(store)([b"HDEL", b"u", b"b"])
    parsed = parse_hgetall_reply(make_hgetall(store)([b"HGETALL", b"u"]))
    assert parsed == {b"a": b"1", b"c": b"3"}


# ---------------------------------------------------------------------------
# HEXISTS
# ---------------------------------------------------------------------------


def test_hexists_present_field_returns_1() -> None:
    store = make_store()
    make_hset(store)([b"HSET", b"u", b"name", b"alice"])
    assert make_hexists(store)([b"HEXISTS", b"u", b"name"]) == b":1\r\n"


def test_hexists_missing_field_returns_0() -> None:
    store = make_store()
    make_hset(store)([b"HSET", b"u", b"name", b"alice"])
    assert make_hexists(store)([b"HEXISTS", b"u", b"missing"]) == b":0\r\n"


def test_hexists_missing_key_returns_0() -> None:
    store = make_store()
    assert make_hexists(store)([b"HEXISTS", b"missing", b"f"]) == b":0\r\n"


# ---------------------------------------------------------------------------
# HLEN
# ---------------------------------------------------------------------------


def test_hlen_missing_key_returns_0() -> None:
    store = make_store()
    assert make_hlen(store)([b"HLEN", b"missing"]) == b":0\r\n"


def test_hlen_returns_field_count() -> None:
    store = make_store()
    make_hset(store)([b"HSET", b"u", b"a", b"1", b"b", b"2", b"c", b"3"])
    assert make_hlen(store)([b"HLEN", b"u"]) == b":3\r\n"


# ---------------------------------------------------------------------------
# Type discipline
# ---------------------------------------------------------------------------


def test_hset_on_string_key_raises_wrongtype() -> None:
    store = make_store()
    make_set(store)([b"SET", b"foo", b"bar"])
    with pytest.raises(WrongTypeError):
        make_hset(store)([b"HSET", b"foo", b"f", b"v"])


def test_hget_on_list_key_raises_wrongtype() -> None:
    store = make_store()
    make_rpush(store)([b"RPUSH", b"l", b"a"])
    with pytest.raises(WrongTypeError):
        make_hget(store)([b"HGET", b"l", b"f"])


# ---------------------------------------------------------------------------
# Encoding transitions (used later by OBJECT ENCODING in T23)
# ---------------------------------------------------------------------------


def test_small_hash_encoding_is_listpack() -> None:
    store = make_store()
    make_hset(store)([b"HSET", b"u", b"a", b"1", b"b", b"2"])
    obj = store.get_object(b"u")
    assert obj is not None
    assert obj.encoding == "listpack"


def test_large_hash_encoding_flips_to_hashtable() -> None:
    store = make_store()
    args: list[bytes] = [b"HSET", b"u"]
    for i in range(200):
        args.append(f"field{i}".encode())
        args.append(b"v")
    make_hset(store)(args)
    obj = store.get_object(b"u")
    assert obj is not None
    assert obj.encoding == "hashtable"

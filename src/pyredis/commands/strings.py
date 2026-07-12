from pyredis.encoder import encode_bulk, encode_integer, encode_simple_string
from pyredis.object import RedisObject
from pyredis.store import KeyValueStore

from pyredis.commands import CommandEntry, HandlerFunc


def make_set(store: KeyValueStore) -> HandlerFunc:
    def handle_set(args: list[bytes]) -> bytes:
        key, value = args[1], args[2]
        store.put(key, RedisObject(type="string", value=value))
        return encode_simple_string("OK")
    return handle_set


def make_get(store: KeyValueStore) -> HandlerFunc:
    def handle_get(args: list[bytes]) -> bytes:
        obj = store.get_or_raise(args[1], "string")
        if obj is None:
            return encode_bulk(None)
        assert isinstance(obj.value, bytes)
        return encode_bulk(obj.value)
    return handle_get


def make_del(store: KeyValueStore) -> HandlerFunc:
    def handle_del(args: list[bytes]) -> bytes:
        return encode_integer(store.delete(*args[1:]))
    return handle_del


def make_exists(store: KeyValueStore) -> HandlerFunc:
    def handle_exists(args: list[bytes]) -> bytes:
        return encode_integer(store.exists(*args[1:]))
    return handle_exists


def make_type(store: KeyValueStore) -> HandlerFunc:
    def handle_type(args: list[bytes]) -> bytes:
        obj = store.get_object(args[1])
        if obj is None:
            return encode_simple_string("none")
        return encode_simple_string(obj.type)
    return handle_type


def register(store: KeyValueStore, table: dict[bytes, CommandEntry]) -> None:
    table[b"SET"] = CommandEntry(make_set(store), 3, -1, frozenset({"write", "denyoom"}), 1, 1)
    table[b"GET"] = CommandEntry(make_get(store), 2,  2, frozenset({"readonly", "fast"}), 1, 1)
    table[b"DEL"] = CommandEntry(make_del(store), 2, -1, frozenset({"write"}),            1, -1)
    table[b"EXISTS"] = CommandEntry(make_exists(store), 2, -1, frozenset({"readonly", "fast"}), 1, -1)
    table[b"TYPE"] = CommandEntry(make_type(store), 2,  2, frozenset({"readonly", "fast"}), 1, 1)

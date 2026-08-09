from pyredis.commands import CommandEntry, HandlerFunc
from pyredis.encoder import encode_array, encode_bulk, encode_integer
from pyredis.errors import CommandError
from pyredis.object import RedisObject
from pyredis.store import KeyValueStore

_HASH_MAX_LISTPACK_ENTRIES = 128


def _maybe_update_encoding(obj: RedisObject) -> None:
    assert isinstance(obj.value, dict)
    if len(obj.value) > _HASH_MAX_LISTPACK_ENTRIES:
        obj.encoding = "hashtable"
    else:
        obj.encoding = "listpack"


def make_hset(store: KeyValueStore) -> HandlerFunc:
    def handle_hset(args: list[bytes]) -> bytes:
        if len(args) < 4 or (len(args) - 2) % 2 != 0:
            raise CommandError("ERR wrong number of arguments for 'hset' command")
        key = args[1]
        obj = store.get_or_raise(key, "hash")
        if obj is None:
            obj = RedisObject(type="hash", value={})
            store.put(key, obj)
        assert isinstance(obj.value, dict)
        added = 0
        for i in range(2, len(args), 2):
            field, value = args[i], args[i + 1]
            if field not in obj.value:
                added += 1
            obj.value[field] = value
        _maybe_update_encoding(obj)
        return encode_integer(added)
    return handle_hset


def make_hget(store: KeyValueStore) -> HandlerFunc:
    def handle_hget(args: list[bytes]) -> bytes:
        obj = store.get_or_raise(args[1], "hash")
        if obj is None:
            return encode_bulk(None)
        assert isinstance(obj.value, dict)
        return encode_bulk(obj.value.get(args[2]))
    return handle_hget


def make_hdel(store: KeyValueStore) -> HandlerFunc:
    def handle_hdel(args: list[bytes]) -> bytes:
        key = args[1]
        obj = store.get_or_raise(key, "hash")
        if obj is None:
            return encode_integer(0)
        assert isinstance(obj.value, dict)
        removed = 0
        for field in args[2:]:
            if field in obj.value:
                del obj.value[field]
                removed += 1
        if not obj.value:
            store.delete(key)
        return encode_integer(removed)
    return handle_hdel


def make_hgetall(store: KeyValueStore) -> HandlerFunc:
    def handle_hgetall(args: list[bytes]) -> bytes:
        obj = store.get_or_raise(args[1], "hash")
        if obj is None:
            return encode_array([])
        assert isinstance(obj.value, dict)
        flat: list[bytes] = []
        for field, value in obj.value.items():
            flat.append(field)
            flat.append(value)
        return encode_array(list(flat))
    return handle_hgetall


def make_hexists(store: KeyValueStore) -> HandlerFunc:
    def handle_hexists(args: list[bytes]) -> bytes:
        obj = store.get_or_raise(args[1], "hash")
        if obj is None:
            return encode_integer(0)
        assert isinstance(obj.value, dict)
        return encode_integer(1 if args[2] in obj.value else 0)
    return handle_hexists


def make_hlen(store: KeyValueStore) -> HandlerFunc:
    def handle_hlen(args: list[bytes]) -> bytes:
        obj = store.get_or_raise(args[1], "hash")
        if obj is None:
            return encode_integer(0)
        assert isinstance(obj.value, dict)
        return encode_integer(len(obj.value))
    return handle_hlen


def register(store: KeyValueStore, table: dict[bytes, CommandEntry]) -> None:
    table[b"HSET"]    = CommandEntry(make_hset(store),    4, -1, frozenset({"write", "denyoom"}), 1, 1)
    table[b"HGET"]    = CommandEntry(make_hget(store),    3,  3, frozenset({"readonly", "fast"}), 1, 1)
    table[b"HDEL"]    = CommandEntry(make_hdel(store),    3, -1, frozenset({"write", "fast"}),    1, 1)
    table[b"HGETALL"] = CommandEntry(make_hgetall(store), 2,  2, frozenset({"readonly"}),         1, 1)
    table[b"HEXISTS"] = CommandEntry(make_hexists(store), 3,  3, frozenset({"readonly", "fast"}), 1, 1)
    table[b"HLEN"]    = CommandEntry(make_hlen(store),    2,  2, frozenset({"readonly", "fast"}), 1, 1)

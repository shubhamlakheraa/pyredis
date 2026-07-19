import time

from pyredis.encoder import encode_bulk, encode_integer, encode_simple_string
from pyredis.object import RedisObject
from pyredis.store import KeyValueStore
from pyredis.errors import CommandError
from pyredis.commands import CommandEntry, HandlerFunc



def parse_integer_value(obj : RedisObject | None) -> int:
    if obj is None :
        return 0
    assert isinstance(obj.value, bytes)
    try :
        return int(obj.value)
    except ValueError :
        raise CommandError("ERR value is not an integer or out of range")




def make_set(store: KeyValueStore) -> HandlerFunc:
    def handle_set(args: list[bytes]) -> bytes:
        key, value = args[1], args[2]
        store.put(key, RedisObject(type="string", value=value))
        store.remove_expiry(key)  # plain SET clears any existing TTL
        i = 3
        while i < len(args):
            opt = args[i].upper()
            if opt == b"EX":
                try:
                    seconds = int(args[i + 1])
                except (ValueError, IndexError):
                    raise CommandError("ERR syntax error")
                if seconds <= 0:
                    raise CommandError("ERR invalid expire time in 'set' command")
                store.set_expiry(key, time.time() + seconds)
                i += 2
            elif opt == b"PX":
                try:
                    ms = int(args[i + 1])
                except (ValueError, IndexError):
                    raise CommandError("ERR syntax error")
                if ms <= 0:
                    raise CommandError("ERR invalid expire time in 'set' command")
                store.set_expiry(key, time.time() + ms / 1000.0)
                i += 2
            else:
                raise CommandError("ERR syntax error")
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

INT64_MAX =  9_223_372_036_854_775_807   # 2**63 - 1
INT64_MIN = -9_223_372_036_854_775_808   # -2**63


def _store_int(store: KeyValueStore, key: bytes, value: int) -> None:
    store.put(key, RedisObject(type="string", value=str(value).encode()))


def make_incr(store: KeyValueStore) -> HandlerFunc:
    def handle_incr(args: list[bytes]) -> bytes:
        obj = store.get_or_raise(args[1], "string")
        result = parse_integer_value(obj) + 1
        if result > INT64_MAX:
            raise CommandError("ERR increment or decrement would overflow")
        _store_int(store, args[1], result)
        return encode_integer(result)
    return handle_incr


def make_decr(store: KeyValueStore) -> HandlerFunc:
    def handle_decr(args: list[bytes]) -> bytes:
        obj = store.get_or_raise(args[1], "string")
        result = parse_integer_value(obj) - 1
        if result < INT64_MIN:
            raise CommandError("ERR increment or decrement would overflow")
        _store_int(store, args[1], result)
        return encode_integer(result)
    return handle_decr


def make_incrby(store: KeyValueStore) -> HandlerFunc:
    def handle_incrby(args: list[bytes]) -> bytes:
        try:
            delta = int(args[2])
        except ValueError:
            raise CommandError("ERR value is not an integer or out of range")
        obj = store.get_or_raise(args[1], "string")
        result = parse_integer_value(obj) + delta
        if result > INT64_MAX or result < INT64_MIN:
            raise CommandError("ERR increment or decrement would overflow")
        _store_int(store, args[1], result)
        return encode_integer(result)
    return handle_incrby


def make_decrby(store: KeyValueStore) -> HandlerFunc:
    def handle_decrby(args: list[bytes]) -> bytes:
        try:
            delta = int(args[2])
        except ValueError:
            raise CommandError("ERR value is not an integer or out of range")
        obj = store.get_or_raise(args[1], "string")
        result = parse_integer_value(obj) - delta
        if result > INT64_MAX or result < INT64_MIN:
            raise CommandError("ERR increment or decrement would overflow")
        _store_int(store, args[1], result)
        return encode_integer(result)
    return handle_decrby







def register(store: KeyValueStore, table: dict[bytes, CommandEntry]) -> None:
    table[b"SET"]    = CommandEntry(make_set(store),    3, -1, frozenset({"write", "denyoom"}), 1, 1)
    table[b"GET"]    = CommandEntry(make_get(store),    2,  2, frozenset({"readonly", "fast"}), 1, 1)
    table[b"DEL"]    = CommandEntry(make_del(store),    2, -1, frozenset({"write"}),            1, -1)
    table[b"EXISTS"] = CommandEntry(make_exists(store), 2, -1, frozenset({"readonly", "fast"}), 1, -1)
    table[b"TYPE"]   = CommandEntry(make_type(store),   2,  2, frozenset({"readonly", "fast"}), 1, 1)
    table[b"INCR"]   = CommandEntry(make_incr(store),   2,  2, frozenset({"write", "denyoom"}), 1, 1)
    table[b"DECR"]   = CommandEntry(make_decr(store),   2,  2, frozenset({"write", "denyoom"}), 1, 1)
    table[b"INCRBY"] = CommandEntry(make_incrby(store), 3,  3, frozenset({"write", "denyoom"}), 1, 1)
    table[b"DECRBY"] = CommandEntry(make_decrby(store), 3,  3, frozenset({"write", "denyoom"}), 1, 1)

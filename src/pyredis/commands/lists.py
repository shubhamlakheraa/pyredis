from collections import deque

from pyredis.commands import CommandEntry, HandlerFunc
from pyredis.encoder import encode_array, encode_bulk, encode_integer
from pyredis.errors import CommandError
from pyredis.object import RedisObject
from pyredis.store import KeyValueStore


_LIST_MAX_LISTPACK_SIZE = 128

def make_lpush(store: KeyValueStore) -> HandlerFunc:
    def handle_lpush(args: list[bytes]) -> bytes:
        key = args[1]
        obj = store.get_or_raise(key, "list")  
        if obj is None :
            obj = RedisObject(type="list", value=deque())
            store.put(key, obj)
        assert isinstance(obj.value, deque)
        for value in args[2:]:
            obj.value.appendleft(value)
        _maybe_update_encoding(obj)
        return encode_integer(len(obj.value)) 
    return handle_lpush

def make_rpush(store: KeyValueStore) -> HandlerFunc:
    def handle_rpush(args: list[bytes]) -> bytes:
        key = args[1]
        obj = store.get_or_raise(key, "list")  
        if obj is None :
            obj = RedisObject(type="list", value=deque())
            store.put(key, obj)
        assert isinstance(obj.value, deque)
        for value in args[2:]:
            obj.value.append(value)
        _maybe_update_encoding(obj)
        return encode_integer(len(obj.value)) 
    return handle_rpush


def make_lpop(store: KeyValueStore) -> HandlerFunc:
    def handle_lpop(args: list[bytes]) -> bytes:
        key = args[1]
        obj = store.get_or_raise(key, "list")
        if obj is None :
            return encode_bulk(None)
        assert isinstance(obj.value, deque)
        if not obj.value:
            return encode_bulk(None)
        value = obj.value.popleft()
        if not obj.value:
            store.delete(key)
        return encode_bulk(value)
    return handle_lpop

def make_rpop(store: KeyValueStore) -> HandlerFunc:
    def handle_rpop(args: list[bytes]) -> bytes:
        key = args[1]
        obj = store.get_or_raise(key, "list")
        if obj is None :
            return encode_bulk(None)
        assert isinstance(obj.value, deque)
        if not obj.value:
            return encode_bulk(None)
        value = obj.value.pop()
        if not obj.value:
            store.delete(key)
        return encode_bulk(value)
    return handle_rpop


def make_llen(store: KeyValueStore) -> HandlerFunc:
    def handle_llen(args: list[bytes]) -> bytes:
        key = args[1]
        obj = store.get_or_raise(key, "list")
        if obj is None :
            return encode_integer(0)
        assert isinstance(obj.value, deque)
        return encode_integer(len(obj.value))
    return handle_llen

def make_lrange(store: KeyValueStore) -> HandlerFunc:
    def handle_lrange(args: list[bytes]) -> bytes :
        key = args[1]
        try :
            start = int(args[2])
            stop = int(args[3])
        except ValueError :
            raise CommandError("ERR value is not an integer or out of range")
        obj = store.get_or_raise(key, "list")
        if obj is None :
            return encode_array([])
        assert isinstance(obj.value, deque)
        length = len(obj.value)
        if start < 0 :
            start = max(length + start, 0)
        if stop < 0 :
            stop += length
        stop = min(stop, length - 1)
        if start > stop or start >= length :
            return encode_array([])
        result = list(obj.value)[start:stop + 1]
        return encode_array(list(result))
    return handle_lrange




def register(store: KeyValueStore, table: dict[bytes, CommandEntry]) -> None:
    table[b"LPUSH"]  = CommandEntry(make_lpush(store),  3, -1, frozenset({"write", "denyoom"}), 1, 1)
    table[b"RPUSH"]  = CommandEntry(make_rpush(store),  3, -1, frozenset({"write", "denyoom"}), 1, 1)
    table[b"LPOP"]   = CommandEntry(make_lpop(store),   2,  2, frozenset({"write", "fast"}),    1, 1)
    table[b"RPOP"]   = CommandEntry(make_rpop(store),   2,  2, frozenset({"write", "fast"}),    1, 1)
    table[b"LLEN"]   = CommandEntry(make_llen(store),   2,  2, frozenset({"readonly", "fast"}), 1, 1)
    table[b"LRANGE"] = CommandEntry(make_lrange(store), 4,  4, frozenset({"readonly"}),         1, 1)

def _maybe_update_encoding (obj: RedisObject) -> None :
    assert isinstance(obj.value, deque)
    if len(obj.value) >  _LIST_MAX_LISTPACK_SIZE :
        obj.encoding = "quicklist"
    else :
        obj.encoding = "listpack"

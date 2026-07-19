import time

from pyredis.encoder import encode_integer
from pyredis.store import KeyValueStore
from pyredis.errors import CommandError
from pyredis.commands import CommandEntry, HandlerFunc


def make_expire(store: KeyValueStore) -> HandlerFunc:
    def handle_expire(args: list[bytes]) -> bytes:
        key = args[1]
        try:
            seconds = int(args[2])
        except ValueError:
            raise CommandError("ERR value is not an integer or out of range")
        if seconds <= 0:
            raise CommandError("ERR invalid expire time in 'expire' command")
        if store.get_object(key) is None:
            return encode_integer(0)
        store.set_expiry(key, time.time() + seconds)
        return encode_integer(1)
    return handle_expire


def make_pexpire(store: KeyValueStore) -> HandlerFunc:
    def handle_pexpire(args: list[bytes]) -> bytes:
        key = args[1]
        try:
            ms = int(args[2])
        except ValueError:
            raise CommandError("ERR value is not an integer or out of range")
        if ms <= 0:
            raise CommandError("ERR invalid expire time in 'pexpire' command")
        if store.get_object(key) is None:
            return encode_integer(0)
        store.set_expiry(key, time.time() + ms / 1000.0)
        return encode_integer(1)
    return handle_pexpire


def make_ttl(store: KeyValueStore) -> HandlerFunc:
    def handle_ttl(args: list[bytes]) -> bytes:
        key = args[1]
        if store.get_object(key) is None:
            return encode_integer(-2)
        deadline = store.get_expiry(key)
        if deadline is None:
            return encode_integer(-1)
        remaining = deadline - time.time()
        return encode_integer(max(0, int(remaining)))
    return handle_ttl


def make_pttl(store: KeyValueStore) -> HandlerFunc:
    def handle_pttl(args: list[bytes]) -> bytes:
        key = args[1]
        if store.get_object(key) is None:
            return encode_integer(-2)
        deadline = store.get_expiry(key)
        if deadline is None:
            return encode_integer(-1)
        remaining_ms = (deadline - time.time()) * 1000
        return encode_integer(max(0, int(remaining_ms)))
    return handle_pttl


def make_persist(store: KeyValueStore) -> HandlerFunc:
    def handle_persist(args: list[bytes]) -> bytes:
        key = args[1]
        if store.get_object(key) is None:
            return encode_integer(0)
        if store.get_expiry(key) is None:
            return encode_integer(0)
        store.remove_expiry(key)
        return encode_integer(1)
    return handle_persist


def register(store: KeyValueStore, table: dict[bytes, CommandEntry]) -> None:
    table[b"EXPIRE"]  = CommandEntry(make_expire(store),  3, 3, frozenset({"write"}),            1, 1)
    table[b"PEXPIRE"] = CommandEntry(make_pexpire(store), 3, 3, frozenset({"write"}),            1, 1)
    table[b"TTL"]     = CommandEntry(make_ttl(store),     2, 2, frozenset({"readonly", "fast"}), 1, 1)
    table[b"PTTL"]    = CommandEntry(make_pttl(store),    2, 2, frozenset({"readonly", "fast"}), 1, 1)
    table[b"PERSIST"] = CommandEntry(make_persist(store), 2, 2, frozenset({"write"}),            1, 1)

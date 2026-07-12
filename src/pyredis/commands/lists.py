from pyredis.errors import CommandError
from pyredis.store import KeyValueStore

from pyredis.commands import CommandEntry, HandlerFunc


def make_lpush(store: KeyValueStore) -> HandlerFunc:
    def handle_lpush(args: list[bytes]) -> bytes:
        store.get_or_raise(args[1], "list")  # raises WrongTypeError if key is wrong type
        raise CommandError("ERR LPUSH not implemented yet")
    return handle_lpush


def register(store: KeyValueStore, table: dict[bytes, CommandEntry]) -> None:
    table[b"LPUSH"] = CommandEntry(make_lpush(store), 3, -1, frozenset({"write", "denyoom"}), 1, 1)

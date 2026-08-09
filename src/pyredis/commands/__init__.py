from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Callable

from pyredis.commands.ping import handle_echo, handle_ping

if TYPE_CHECKING:
    from pyredis.store import KeyValueStore

HandlerFunc = Callable[[list[bytes]], bytes]


@dataclass(frozen=True)
class CommandEntry:
    handler: HandlerFunc
    arity_min: int
    arity_max: int  # -1 means variadic (no upper bound)
    flags: frozenset[str]
    first_key: int
    last_key: int


def create_command_table(store: KeyValueStore) -> dict[bytes, CommandEntry]:
    from pyredis.commands import expiry, hashes, lists, strings

    table: dict[bytes, CommandEntry] = {
        b"PING": CommandEntry(handle_ping, 1, 2, frozenset({"fast"}), 0, 0),
        b"ECHO": CommandEntry(handle_echo, 2, 2, frozenset({"fast"}), 0, 0),
    }
    strings.register(store, table)
    lists.register(store, table)
    expiry.register(store, table)
    hashes.register(store, table)
    return table

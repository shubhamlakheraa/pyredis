from dataclasses import dataclass
from typing import Callable

from pyredis.commands.ping import handle_echo, handle_ping

HandlerFunc = Callable[[list[bytes]], bytes]


@dataclass(frozen=True)
class CommandEntry:
    handler: HandlerFunc
    arity_min: int
    arity_max: int  # -1 means variadic (no upper bound)


def create_command_table() -> dict[bytes, CommandEntry]:
    return {
        b"PING": CommandEntry(handle_ping, arity_min=1, arity_max=2),
        b"ECHO": CommandEntry(handle_echo, arity_min=2, arity_max=2),
    }
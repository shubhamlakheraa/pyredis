class RedisError(Exception):
    """Base for all pyredis errors. The dispatcher catches this and writes -ERR to the client."""


class CommandError(RedisError):
    """Unknown or malformed command."""


class ProtocolError(RedisError):
    """Malformed RESP input from the client."""

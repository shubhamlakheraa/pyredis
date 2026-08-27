# pyredis

A from-scratch Redis-compatible server written in Python — built one task at a
time as a systems-programming exercise. The goal is not "another Redis client"
but to actually understand *why* Redis is designed the way it is: the RESP
protocol, the single-threaded reactor, the typed keyspace, lazy + active
expiry, and the encoding transitions that let one data type live cheaply when
small and scale when large.

Every commit corresponds to a numbered task (T01, T02, ...) with a specific
learning goal. This README summarizes what is built so far and how the pieces
fit together.

## Status

**Completed:** T01 – T13
**Tests:** 175 passing, `mypy --strict` clean across 16 source files
**Runtime:** single-threaded reactor, non-blocking sockets, `selectors`-based
event loop

## What works today

You can start the server and drive it with `redis-cli` or any RESP client:

```
uv run pyredis          # listens on 127.0.0.1:6379 by default
```

Commands currently implemented:

| Family     | Commands                                                       |
|------------|----------------------------------------------------------------|
| Connection | `PING`, `ECHO`                                                 |
| Strings    | `SET` (with `EX`/`PX`), `GET`, `DEL`, `EXISTS`, `TYPE`         |
| Counters   | `INCR`, `DECR`, `INCRBY`, `DECRBY`                             |
| Expiry     | `EXPIRE`, `PEXPIRE`, `TTL`, `PTTL`, `PERSIST`                  |
| Lists      | `LPUSH`, `RPUSH`, `LPOP`, `RPOP`, `LLEN`, `LRANGE`             |
| Hashes     | `HSET`, `HGET`, `HDEL`, `HGETALL`, `HEXISTS`, `HLEN`           |

## Architecture

### The reactor loop (T02 – T04)

The server runs on **one thread**. A single `selectors.DefaultSelector`
watches the listening socket and every client socket. On each `select()`
wakeup the loop:

1. Runs one bounded **active expiry cycle** (see below).
2. For each ready file descriptor, either `accept()` a new connection or
   read from / write to an existing one.

Sockets are non-blocking, so `recv()` returns whatever is in the OS buffer
right now — which may be less than one command. Each `RedisConnection`
therefore owns two byte buffers:

- an **inbound buffer** appended to on every read; the RESP parser walks it
  looking for complete frames and leaves partial ones in place;
- an **outbound buffer** the encoder writes into; the loop drains it into
  `send()` only when the socket signals writable.

Because there is only one thread, every command executes to completion
before the next event is processed. That is the source of Redis's famous
atomicity: `INCR` is atomic not because of a lock, but because nothing else
can run *at all* while it does.

### RESP protocol (T05 – T06)

`src/pyredis/resp.py` decodes the wire format — arrays of bulk strings —
into `list[bytes]`. The parser is cursor-threaded end-to-end: instead of
re-scanning from position 0 after each frame (which would misbehave under
pipelining), it returns `(args, n_bytes_consumed)` and the connection
`consume(n)`s exactly that many bytes.

`src/pyredis/encoder.py` handles the reply side. The `RespValue` union
covers every reply shape (`bytes | None | int | list[RespValue]`) and one
recursive `encode_array` covers nested replies (used heavily by `LRANGE`,
`HGETALL`, etc.).

### Command dispatch table (T07)

Commands are entries in a table, not a giant `if/elif`. Each entry is a
`CommandEntry` dataclass carrying the handler, arity bounds, a flag set
(`readonly`, `write`, `fast`, `denyoom`, ...), and the key positions
(`first_key`, `last_key`) so the introspection command `COMMAND` (planned
for T23) can report them.

`server._dispatch` upcases the command name, looks it up, validates arity,
then calls the handler. Errors raised by handlers (e.g.
`WrongTypeError`, `CommandError`) are caught and encoded as RESP error
frames.

### Keyspace and RedisObject (T08)

Values are not stored raw. Every key maps to a `RedisObject` envelope:

```python
@dataclass
class RedisObject:
    type: RedisSupportedTypes    # "string" | "list" | "hash" | "set" | "zset"
    value: object                # the actual data — bytes, deque, dict, ...
    encoding: str = "raw"        # "listpack" | "hashtable" | "intset" | ...
    expire_at: float | None = None
    last_access: float = ...
```

`KeyValueStore` is the sole owner of `_data: dict[bytes, RedisObject]`.
It exposes a `get_object` accessor that is the *only* read path — this
matters because the lazy-expiry check lives there, so no command can
observe a dead key. `get_or_raise(key, expected_type)` layers a type
check on top and raises `WrongTypeError` on mismatch, which is how
`LPUSH stringkey x` returns `-WRONGTYPE` without every command duplicating
the check.

### Expiry: lazy + active (T10 – T11)

`KeyValueStore` keeps a **separate** `_expires: dict[bytes, float]`
mapping key → absolute unix deadline. It is separate from `_data` because
most keys have no TTL — putting an `expire_at` field on every RedisObject
would burn memory on a mostly-empty field.

Two cooperating mechanisms honor deadlines:

- **Lazy** — every call to `get_object` compares `time.time()` against the
  key's deadline and evicts it inline. This is exact-on-access but leaks
  memory for keys that are never read again.

- **Active** — `active_expire_cycle()` runs at the top of every event-loop
  iteration. It samples 20 random keys from `_expires`, deletes the dead
  ones, and re-runs if the dead ratio exceeded 25% — with a hard 25ms
  wall-clock cap so it never stalls client I/O. This is probabilistic,
  not exact: the trade is bounded latency for eventual (not instant)
  cleanup.

### Collection encodings (T12 – T13)

Redis stores small collections compactly and promotes to a "real"
structure only when they grow. pyredis's backing store is uniform (a
`deque` for lists, a `dict` for hashes), but each `RedisObject` carries an
`encoding` string that flips at the size threshold:

| Type | Small (compact)     | Large              | Threshold |
|------|---------------------|--------------------|-----------|
| list | `"listpack"`        | `"quicklist"`      | 128 items |
| hash | `"listpack"`        | `"hashtable"`      | 128 fields|

This flag is honest metadata even though the underlying container never
changes — when `OBJECT ENCODING` lands in T23 it will report something
real.

Both types enforce the **empty-after-delete** invariant: popping the last
element of a list or deleting the last field of a hash removes the whole
key. `EXISTS` on an emptied collection must return 0.

## Layout

```
src/pyredis/
├── __main__.py             # entry point — parses config, starts server
├── config.py               # host/port dataclass
├── connection.py           # RedisConnection: socket + in/out buffers
├── encoder.py              # RESP encoding
├── errors.py               # RedisError hierarchy (Protocol, Command, WrongType)
├── object.py               # RedisObject envelope
├── resp.py                 # RESP decoding (cursor-threaded)
├── server.py               # reactor loop + dispatch
├── store.py                # KeyValueStore, _expires, active_expire_cycle
└── commands/
    ├── __init__.py         # CommandEntry + create_command_table
    ├── ping.py             # PING, ECHO handlers
    ├── strings.py          # SET/GET/DEL/EXISTS/TYPE + counters
    ├── expiry.py           # EXPIRE/PEXPIRE/TTL/PTTL/PERSIST
    ├── lists.py            # LPUSH/RPUSH/LPOP/RPOP/LLEN/LRANGE
    └── hashes.py           # HSET/HGET/HDEL/HGETALL/HEXISTS/HLEN

tests/                      # 175 pytest tests, one file per module
```

## Design decisions worth calling out

- **Factory pattern for handlers.** Each command's `make_xxx(store)` closes
  over the store and returns a `HandlerFunc` with signature
  `list[bytes] -> bytes`. The dispatcher never sees the store — it just
  calls handlers. This keeps `CommandEntry` uniform regardless of what
  state a command needs.

- **One accessor to rule them all.** Every read goes through
  `KeyValueStore.get_object`. That is the reason lazy expiry, type
  checking, and (later) LRU touch can be plumbed in one place.

- **Cursor-threaded RESP parsing.** Each parsing helper receives a
  cursor and returns `(value, new_cursor)`. Under pipelining the parser
  extracts multiple commands from one buffer without ever re-scanning
  bytes it has already looked at.

- **No premature abstraction.** Handlers are direct — no service layer, no
  DI container, no interfaces for one implementation. If T15 introduces a
  second backing structure, that's when the abstraction earns its place.

## Running

```
uv sync                     # install dev deps
uv run pyredis              # start the server
uv run pytest -q            # run tests
uv run mypy --strict src/   # type-check
```

Once running, drive it with any RESP client:

```
redis-cli -p 6379
> SET foo bar EX 10
OK
> TTL foo
(integer) 10
> RPUSH mylist a b c
(integer) 3
> LRANGE mylist 0 -1
1) "a"
2) "b"
3) "c"
> HSET user:1 name alice age 26
(integer) 2
> HGETALL user:1
1) "name"
2) "alice"
3) "age"
4) "26"
```

## Roadmap

Upcoming work (from the task plan):

- **T14** — Sets: `SADD`/`SREM`/`SMEMBERS`/`SISMEMBER`/`SINTER`/`SCARD`
  with the intset ↔ hashtable encoding transition.
- **T15** — Sorted sets and a hand-written skip list.
- **T20+** — Persistence (RDB/AOF), replication, `OBJECT` introspection.

Each task ships with a full commit, a passing test suite, and a clean
`mypy --strict` run.

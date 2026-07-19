import time

from pyredis.object import RedisObject
from pyredis.store import KeyValueStore


def make_store() -> KeyValueStore:
    return KeyValueStore()


def string_obj() -> RedisObject:
    return RedisObject(type="string", value=b"v")


# ---------------------------------------------------------------------------
# Basic correctness
# ---------------------------------------------------------------------------


def test_cycle_deletes_expired_keys() -> None:
    store = make_store()
    for i in range(100):
        key = f"k{i}".encode()
        store.put(key, string_obj())
        store.set_expiry(key, time.time() - 1)  # already dead
    deleted = store.active_expire_cycle()
    assert deleted > 0


def test_cycle_leaves_live_keys() -> None:
    store = make_store()
    store.put(b"k", string_obj())
    store.set_expiry(b"k", time.time() + 100)
    store.active_expire_cycle()
    assert store.get_object(b"k") is not None


def test_cycle_empty_expires_is_noop() -> None:
    store = make_store()
    store.put(b"k", string_obj())  # key with no TTL
    assert store.active_expire_cycle() == 0


def test_cycle_returns_zero_when_no_expires() -> None:
    store = make_store()
    assert store.active_expire_cycle() == 0


# ---------------------------------------------------------------------------
# Time budget
# ---------------------------------------------------------------------------


def test_cycle_bounded_by_time() -> None:
    store = make_store()
    for i in range(10_000):
        key = f"k{i}".encode()
        store.put(key, string_obj())
        store.set_expiry(key, time.time() - 1)  # all dead
    start = time.time()
    store.active_expire_cycle()
    assert time.time() - start < 0.1  # well within budget


# ---------------------------------------------------------------------------
# Multiple cycles drain the dead keys
# ---------------------------------------------------------------------------


def test_multiple_cycles_clear_all_dead_keys() -> None:
    store = make_store()
    for i in range(200):
        key = f"k{i}".encode()
        store.put(key, string_obj())
        store.set_expiry(key, time.time() - 1)
    for _ in range(50):
        store.active_expire_cycle()
    assert len(store._expires) == 0


# ---------------------------------------------------------------------------
# Live and dead keys coexist
# ---------------------------------------------------------------------------


def test_cycle_only_deletes_dead_not_live() -> None:
    store = make_store()
    for i in range(50):
        key = f"dead{i}".encode()
        store.put(key, string_obj())
        store.set_expiry(key, time.time() - 1)
    store.put(b"live", string_obj())
    store.set_expiry(b"live", time.time() + 100)

    for _ in range(20):
        store.active_expire_cycle()

    assert store.get_object(b"live") is not None
    assert len(store._expires) == 1  # only the live key's expiry remains

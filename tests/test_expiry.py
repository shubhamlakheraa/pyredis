import time

from pyredis.commands.expiry import (
    make_expire,
    make_persist,
    make_pexpire,
    make_pttl,
    make_ttl,
)
from pyredis.commands.strings import make_get, make_exists, make_set
from pyredis.store import KeyValueStore


def make_store() -> KeyValueStore:
    return KeyValueStore()


# ---------------------------------------------------------------------------
# TTL return codes
# ---------------------------------------------------------------------------


def test_ttl_missing_key_returns_minus2() -> None:
    store = make_store()
    assert make_ttl(store)([b"TTL", b"missing"]) == b":-2\r\n"


def test_ttl_key_with_no_expiry_returns_minus1() -> None:
    store = make_store()
    make_set(store)([b"SET", b"k", b"v"])
    assert make_ttl(store)([b"TTL", b"k"]) == b":-1\r\n"


def test_ttl_key_with_expiry_returns_positive() -> None:
    store = make_store()
    make_set(store)([b"SET", b"k", b"v", b"EX", b"10"])
    result = make_ttl(store)([b"TTL", b"k"])
    # remaining should be between 9 and 10 seconds
    remaining = int(result[1:-2])  # strip leading ':' and trailing '\r\n'
    assert 9 <= remaining <= 10


# ---------------------------------------------------------------------------
# PTTL return codes
# ---------------------------------------------------------------------------


def test_pttl_missing_key_returns_minus2() -> None:
    store = make_store()
    assert make_pttl(store)([b"PTTL", b"missing"]) == b":-2\r\n"


def test_pttl_key_with_no_expiry_returns_minus1() -> None:
    store = make_store()
    make_set(store)([b"SET", b"k", b"v"])
    assert make_pttl(store)([b"PTTL", b"k"]) == b":-1\r\n"


def test_pttl_key_with_expiry_returns_ms() -> None:
    store = make_store()
    make_set(store)([b"SET", b"k", b"v", b"EX", b"10"])
    result = make_pttl(store)([b"PTTL", b"k"])
    remaining_ms = int(result[1:-2])
    assert 9000 <= remaining_ms <= 10000


# ---------------------------------------------------------------------------
# SET EX / PX
# ---------------------------------------------------------------------------


def test_set_ex_sets_ttl() -> None:
    store = make_store()
    make_set(store)([b"SET", b"k", b"v", b"EX", b"10"])
    result = make_ttl(store)([b"TTL", b"k"])
    remaining = int(result[1:-2])
    assert 9 <= remaining <= 10


def test_set_px_sets_ttl_in_ms() -> None:
    store = make_store()
    make_set(store)([b"SET", b"k", b"v", b"PX", b"5000"])
    result = make_pttl(store)([b"PTTL", b"k"])
    remaining_ms = int(result[1:-2])
    assert 4000 <= remaining_ms <= 5000


def test_set_without_ex_clears_previous_ttl() -> None:
    store = make_store()
    make_set(store)([b"SET", b"k", b"v", b"EX", b"10"])
    make_set(store)([b"SET", b"k", b"v2"])  # plain SET — no EX
    assert make_ttl(store)([b"TTL", b"k"]) == b":-1\r\n"


# ---------------------------------------------------------------------------
# EXPIRE / PEXPIRE
# ---------------------------------------------------------------------------


def test_expire_on_existing_key_returns_1() -> None:
    store = make_store()
    make_set(store)([b"SET", b"k", b"v"])
    assert make_expire(store)([b"EXPIRE", b"k", b"10"]) == b":1\r\n"


def test_expire_on_missing_key_returns_0() -> None:
    store = make_store()
    assert make_expire(store)([b"EXPIRE", b"missing", b"10"]) == b":0\r\n"


def test_pexpire_on_existing_key_returns_1() -> None:
    store = make_store()
    make_set(store)([b"SET", b"k", b"v"])
    assert make_pexpire(store)([b"PEXPIRE", b"k", b"5000"]) == b":1\r\n"


def test_pexpire_sets_ttl_in_ms() -> None:
    store = make_store()
    make_set(store)([b"SET", b"k", b"v"])
    make_pexpire(store)([b"PEXPIRE", b"k", b"5000"])
    result = make_pttl(store)([b"PTTL", b"k"])
    remaining_ms = int(result[1:-2])
    assert 4000 <= remaining_ms <= 5000


# ---------------------------------------------------------------------------
# PERSIST
# ---------------------------------------------------------------------------


def test_persist_removes_ttl_returns_1() -> None:
    store = make_store()
    make_set(store)([b"SET", b"k", b"v", b"EX", b"10"])
    assert make_persist(store)([b"PERSIST", b"k"]) == b":1\r\n"
    assert make_ttl(store)([b"TTL", b"k"]) == b":-1\r\n"


def test_persist_on_key_with_no_ttl_returns_0() -> None:
    store = make_store()
    make_set(store)([b"SET", b"k", b"v"])
    assert make_persist(store)([b"PERSIST", b"k"]) == b":0\r\n"


def test_persist_on_missing_key_returns_0() -> None:
    store = make_store()
    assert make_persist(store)([b"PERSIST", b"missing"]) == b":0\r\n"


# ---------------------------------------------------------------------------
# Lazy expiry — the key disappears on access after TTL
# ---------------------------------------------------------------------------


def test_lazy_expiry_get_returns_nil_after_ttl() -> None:
    store = make_store()
    make_set(store)([b"SET", b"k", b"v", b"PX", b"50"])
    time.sleep(0.1)
    assert make_get(store)([b"GET", b"k"]) == b"$-1\r\n"


def test_lazy_expiry_exists_returns_0_after_ttl() -> None:
    store = make_store()
    make_set(store)([b"SET", b"k", b"v", b"PX", b"50"])
    time.sleep(0.1)
    assert make_exists(store)([b"EXISTS", b"k"]) == b":0\r\n"


def test_lazy_expiry_ttl_returns_minus2_after_expiry() -> None:
    store = make_store()
    make_set(store)([b"SET", b"k", b"v", b"PX", b"50"])
    time.sleep(0.1)
    assert make_ttl(store)([b"TTL", b"k"]) == b":-2\r\n"

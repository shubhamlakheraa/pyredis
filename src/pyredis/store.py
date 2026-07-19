import random
import time

from pyredis.errors import WrongTypeError
from pyredis.object import RedisObject, RedisSupportedTypes

_SAMPLE_SIZE = 20
_DEAD_RATIO_THRESHOLD = 0.25
_MAX_CYCLE_SECONDS = 0.025


class KeyValueStore:
    def __init__(self) -> None:
        self._data: dict[bytes, RedisObject] = {}
        self._expires: dict[bytes, float] = {}

    def get_object(self, key: bytes) -> RedisObject | None:
        obj = self._data.get(key)
        if obj is None :
            return None
        deadline = self._expires.get(key)
        if deadline is not None and time.time() >= deadline :
            del self._data[key]
            del self._expires[key]
            return None
        return obj


    def get_or_raise(self, key: bytes, expected_type: RedisSupportedTypes) -> RedisObject | None:
        obj = self.get_object(key)
        if obj is not None and obj.type != expected_type:
            raise WrongTypeError(
                "WRONGTYPE Operation against a key holding the wrong kind of value"
            )
        return obj

    def put(self, key: bytes, obj: RedisObject) -> None:
        self._data[key] = obj

    def delete(self, *keys: bytes) -> int:
        count = 0
        for key in keys:
            if key in self._data:
                del self._data[key]
                self._expires.pop(key, None)
                count += 1
        return count

    def exists(self, *keys: bytes) -> int:
        return sum(1 for key in keys if self.get_object(key) is not None)
    
    def set_expiry(self, key: bytes, deadline: float) -> None:
        self._expires[key] = deadline

    def remove_expiry(self, key: bytes) -> None:
        self._expires.pop(key, None)

    def get_expiry(self, key: bytes) -> float | None:
        return self._expires.get(key)

    def active_expire_cycle(self) -> int:
        total_deleted = 0
        start = time.time()
        while self._expires:
            keys = list(self._expires)
            sample = random.sample(keys, min(_SAMPLE_SIZE, len(keys)))
            now = time.time()
            dead = 0
            for key in sample:
                deadline = self._expires.get(key)
                if deadline is not None and now >= deadline:
                    self._data.pop(key, None)
                    del self._expires[key]
                    dead += 1
                    total_deleted += 1
            if dead / len(sample) < _DEAD_RATIO_THRESHOLD:
                break
            if time.time() - start >= _MAX_CYCLE_SECONDS:
                break
        return total_deleted
    

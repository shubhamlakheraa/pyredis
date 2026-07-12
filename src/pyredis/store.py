import time

from pyredis.errors import WrongTypeError
from pyredis.object import RedisObject, RedisSupportedTypes


class KeyValueStore:
    def __init__(self) -> None:
        self._data: dict[bytes, RedisObject] = {}

    def get_object(self, key: bytes) -> RedisObject | None:
        obj = self._data.get(key)
        if obj is not None and obj.expire_at is not None:
            if time.time() > obj.expire_at:
                del self._data[key]
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
                count += 1
        return count

    def exists(self, *keys: bytes) -> int:
        return sum(1 for key in keys if self.get_object(key) is not None)

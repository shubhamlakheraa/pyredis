from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Literal

RedisSupportedTypes = Literal["string", "list", "hash", "set", "zset"]


@dataclass
class RedisObject:
    type: RedisSupportedTypes
    value: object
    encoding: str = "raw"
    last_access: float = field(default_factory=time.time)

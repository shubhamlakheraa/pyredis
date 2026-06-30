from dataclasses import dataclass


@dataclass(frozen=True)
class Config:
    host: str = "127.0.0.1"
    port: int = 6379
    maxmemory: int = 0
    maxmemory_policy: str = "noeviction"
    appendonly: bool = False
    save_rules: tuple[tuple[int, int], ...] = ((3600, 1), (300, 100), (60, 10000))

import logging
import signal
from types import FrameType
from typing import Optional

from pyredis.config import Config
from pyredis.server import RedisServer, create_server

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

logger = logging.getLogger(__name__)

_server: Optional[RedisServer] = None


def _handle_sigint(signum: int, frame: Optional[FrameType]) -> None:
    logger.info("Received SIGINT — shutting down")
    if _server is not None:
        _server.stop()


def main() -> None:
    global _server
    config = Config()
    _server = create_server(config)
    signal.signal(signal.SIGINT, _handle_sigint)
    _server.start()

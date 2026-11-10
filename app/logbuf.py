import logging
from collections import deque
from datetime import datetime, timezone


class RingBufferHandler(logging.Handler):
    def __init__(self, maxlen: int = 500) -> None:
        super().__init__()
        self.buffer: deque = deque(maxlen=maxlen)

    def emit(self, record: logging.LogRecord) -> None:
        entry = {
            "ts": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "level": record.levelname,
            "msg": self.format(record),
        }
        self.buffer.append(entry)

    def entries(self, limit: int = 200) -> list:
        return list(self.buffer)[-limit:]

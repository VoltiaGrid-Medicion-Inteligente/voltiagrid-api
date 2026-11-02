import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Protocol

F3_PREFIX = "source=f3/dataset=readings"


def object_key(message: dict, stored_at: datetime) -> str:
    stored_at = stored_at.astimezone(timezone.utc)
    return (
        f"{F3_PREFIX}/ingest_date={stored_at:%Y-%m-%d}/ingest_hour={stored_at:%H}/"
        f"{message['concentrator_id']}_{int(message['sequence']):08d}.json"
    )


class RawWriter(Protocol):
    def write(self, key: str, body: bytes) -> None: ...


class LocalRawWriter:
    """Raw layer in a local folder (docker compose and tests). The folder plays the role of the raw bucket."""

    def __init__(self, root: str | Path):
        self.root = Path(root)

    def write(self, key: str, body: bytes) -> None:
        path = self.root / key
        path.parent.mkdir(parents=True, exist_ok=True)
        # Write to a temporary file and rename: a crash never leaves a half-written object behind.
        fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=".tmp-")
        try:
            with os.fdopen(fd, "wb") as f:
                f.write(body)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp, path)
        except BaseException:
            Path(tmp).unlink(missing_ok=True)
            raise

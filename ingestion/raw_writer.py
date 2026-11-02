"""Where the consumer stores each F3 message in the raw layer (US-29).

Key, as in the *Data lake layout* page of voltiagrid-docs:

    source=f3/dataset=readings/ingest_date=YYYY-MM-DD/ingest_hour=HH/<concentrator>_<sequence>.json

ingest_date and ingest_hour are the UTC time the message was stored, never the time inside the message, so a
resend of old readings lands in today's partition and nothing is overwritten (ADR-007). The body is stored
byte for byte as it arrived.
"""

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


class S3RawWriter:
    """Raw layer in the S3 raw bucket (AWS). Credentials come from the task role or AWS_PROFILE, never from code."""

    def __init__(self, bucket: str, client=None):
        if client is None:
            import boto3

            client = boto3.client("s3")
        self.bucket = bucket
        self.client = client

    def write(self, key: str, body: bytes) -> None:
        # S3 never shows a half-written object: put_object either stores all of it or nothing.
        self.client.put_object(Bucket=self.bucket, Key=key, Body=body, ContentType="application/json")


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

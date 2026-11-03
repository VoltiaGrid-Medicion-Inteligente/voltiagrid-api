"""Consumer that dies like `kill -9` at a chosen point. Used by tests/test_consumer_crash.py (US-29, T-29.4).

    python -m tests.crash_consumer <rabbitmq url> <raw dir> --after-writes N [--on-message ID] [--batch-size B]

os._exit skips every cleanup: no flush, no ACK, no clean close. RabbitMQ only sees the connection drop, exactly as
when the container is killed or the machine loses power.
"""

import argparse
import os

from ingestion.consumer import ReadingConsumer, run
from ingestion.raw_writer import LocalRawWriter


class CrashingWriter(LocalRawWriter):
    def __init__(self, root, after_writes, on_message):
        super().__init__(root)
        self.left = after_writes
        self.on_message = on_message

    def write(self, key, body):
        if self.on_message and self.on_message.encode() in body:
            os._exit(3)  # crash every time this message arrives
        if self.left is not None:
            if self.left == 0:
                os._exit(3)  # crash in the middle of a batch: earlier objects written, nothing acknowledged
            self.left -= 1
        super().write(key, body)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("url")
    p.add_argument("raw_dir")
    p.add_argument("--after-writes", type=int, default=None)
    p.add_argument("--on-message", default=None)
    p.add_argument("--batch-size", type=int, default=20)
    p.add_argument("--prefetch", type=int, default=50)
    a = p.parse_args()
    writer = CrashingWriter(a.raw_dir, a.after_writes, a.on_message)
    consumer = ReadingConsumer(writer, batch_size=a.batch_size, batch_seconds=1, write_workers=1)
    run(a.url, consumer, prefetch=a.prefetch, exit_when_idle=5)


if __name__ == "__main__":
    main()

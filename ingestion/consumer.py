"""F3 consumer: reads both reading queues and stores every message in raw before acknowledging it (US-29).

Rules (ADR-001, ADR-007):
- Manual ACK, only after the message is stored. If the consumer dies before that, RabbitMQ delivers the message
  again to the next consumer: nothing is lost.
- prefetch limits how many unacknowledged messages one consumer holds, so a long resend is shared between
  consumers and a crash returns at most `prefetch` messages to the queue.
- A message that is not valid JSON or does not follow the contract is rejected without requeue: it goes to
  readings.dead to be inspected, it does not block the queue.
- If storing fails, the write is retried a few times; then the message is returned to the queue. After
  DELIVERY_LIMIT deliveries RabbitMQ moves it to readings.dead.
- An exact redelivery (same message_id already stored by this process) is acknowledged without writing again.
  Redeliveries after a restart can still produce a second copy in raw; Spark removes exact duplicates (meter,
  interval and sequence), so they never reach clean.
"""

import json
import logging
import time
from collections import Counter, OrderedDict
from datetime import datetime, timezone
from typing import Callable

import pika

from ingestion.raw_writer import RawWriter, object_key
from ingestion.topology import CONSUMED_QUEUES, declare_topology
from simulators.concentrator.contract import validate

log = logging.getLogger(__name__)

DEFAULT_PREFETCH = 100
WRITE_ATTEMPTS = 3
SEEN_IDS = 100_000


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class RecentIds:
    """The last N message ids this process stored, to ignore exact redeliveries without unbounded memory."""

    def __init__(self, size: int = SEEN_IDS):
        self.size = size
        self._ids: OrderedDict[str, None] = OrderedDict()

    def __contains__(self, message_id: str) -> bool:
        return message_id in self._ids

    def add(self, message_id: str) -> None:
        self._ids[message_id] = None
        if len(self._ids) > self.size:
            self._ids.popitem(last=False)


class ReadingConsumer:
    def __init__(
        self,
        writer: RawWriter,
        clock: Callable[[], datetime] = utc_now,
        sleep: Callable[[float], None] = time.sleep,
        write_attempts: int = WRITE_ATTEMPTS,
    ):
        self.writer = writer
        self.clock = clock
        self.sleep = sleep
        self.write_attempts = write_attempts
        self.seen = RecentIds()
        self.stats: Counter = Counter()
        self.last_message_at = time.monotonic()

    @staticmethod
    def parse(body: bytes) -> dict:
        """Raise ValueError if the body is not a valid reading batch."""
        message = json.loads(body)
        if not isinstance(message, dict):
            raise ValueError("message is not a JSON object")
        validate(message)
        return message

    def store(self, message: dict, body: bytes) -> None:
        key = object_key(message, self.clock())
        for attempt in range(1, self.write_attempts + 1):
            try:
                self.writer.write(key, body)
                return
            except Exception:
                if attempt == self.write_attempts:
                    raise
                log.warning("write of %s failed (attempt %s/%s), retrying", key, attempt, self.write_attempts)
                self.sleep(2 ** (attempt - 1))

    def handle(self, channel, method, properties, body: bytes) -> None:
        """pika callback: one delivery."""
        self.last_message_at = time.monotonic()
        tag = method.delivery_tag
        try:
            message = self.parse(body)
        except ValueError as exc:
            log.error("rejected to readings.dead: %s", str(exc)[:300])
            channel.basic_nack(delivery_tag=tag, requeue=False)
            self.stats["rejected"] += 1
            return

        message_id = message["message_id"]
        if message_id in self.seen:
            channel.basic_ack(delivery_tag=tag)
            self.stats["redelivered"] += 1
            return

        try:
            self.store(message, body)
        except Exception:
            log.exception("could not store %s, returning it to the queue", message_id)
            channel.basic_nack(delivery_tag=tag, requeue=True)
            self.stats["write_failed"] += 1
            return

        channel.basic_ack(delivery_tag=tag)
        self.seen.add(message_id)
        self.stats["stored"] += 1
        self.stats["readings"] += len(message["readings"])


def configure(channel, consumer: ReadingConsumer, prefetch: int = DEFAULT_PREFETCH) -> None:
    """Prefetch, topology and manual-ACK subscriptions to both queues."""
    channel.basic_qos(prefetch_count=prefetch)
    declare_topology(channel)
    for queue in CONSUMED_QUEUES:
        channel.basic_consume(queue=queue, on_message_callback=consumer.handle, auto_ack=False)


def run(
    url: str,
    consumer: ReadingConsumer,
    prefetch: int = DEFAULT_PREFETCH,
    exit_when_idle: float | None = None,
    report_every: float = 60.0,
) -> Counter:
    """Consume until stopped (Ctrl+C or SIGTERM), or until no message arrived for exit_when_idle seconds."""
    connection = pika.BlockingConnection(pika.URLParameters(url))
    channel = connection.channel()
    configure(channel, consumer, prefetch)
    log.info("consuming %s with prefetch=%s", ", ".join(CONSUMED_QUEUES), prefetch)
    last_report = time.monotonic()
    try:
        while True:
            connection.process_data_events(time_limit=1)
            now = time.monotonic()
            if now - last_report >= report_every:
                log.info("stats: %s", dict(consumer.stats))
                last_report = now
            if exit_when_idle is not None and now - consumer.last_message_at >= exit_when_idle:
                log.info("no messages for %ss, exiting", exit_when_idle)
                break
    except KeyboardInterrupt:
        log.info("stopping")
    finally:
        if connection.is_open:
            connection.close()
    log.info("done: %s", dict(consumer.stats))
    return consumer.stats

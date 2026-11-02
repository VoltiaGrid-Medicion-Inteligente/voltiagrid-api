"""F3 consumer: reads both reading queues and stores every message in raw before acknowledging it (US-29).

Rules (ADR-001, ADR-007):
- Manual ACK, only after the message is stored. If the consumer dies before that, RabbitMQ delivers the message
  again to the next consumer: nothing is lost.
- prefetch limits how many unacknowledged messages one consumer holds, so a long resend is shared between
  consumers and a crash returns at most `prefetch` messages to the queue.
- Writes go in batches (T-29.3): messages wait in memory, unacknowledged, until there are `batch_size` of them or
  the oldest waited `batch_seconds`. The batch is written in parallel and then acknowledged with a single
  `basic_ack(multiple=True)`. A crash while they wait loses nothing: they were never acknowledged.
- A message that is not valid JSON or does not follow the contract is rejected without requeue: it goes to
  readings.dead to be inspected, it does not block the queue.
- If storing fails, the write is retried a few times; then the message is returned to the queue. After
  DELIVERY_LIMIT deliveries RabbitMQ moves it to readings.dead.
- An exact redelivery (same message_id already stored or waiting in this process) is acknowledged without writing
  again. Redeliveries after a restart can still produce a second copy in raw; Spark removes exact duplicates
  (meter, interval and sequence), so they never reach clean.
"""

import json
import logging
import time
from collections import Counter, OrderedDict
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Callable

import pika

from ingestion.raw_writer import RawWriter, object_key
from ingestion.topology import CONSUMED_QUEUES, declare_topology
from simulators.concentrator.contract import validate

log = logging.getLogger(__name__)

DEFAULT_PREFETCH = 100
DEFAULT_BATCH_SIZE = 50
DEFAULT_BATCH_SECONDS = 2.0
DEFAULT_WRITE_WORKERS = 8
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


@dataclass
class Pending:
    tag: int
    message_id: str
    readings: int
    key: str
    body: bytes


class ReadingConsumer:
    def __init__(
        self,
        writer: RawWriter,
        batch_size: int = DEFAULT_BATCH_SIZE,
        batch_seconds: float = DEFAULT_BATCH_SECONDS,
        write_workers: int = DEFAULT_WRITE_WORKERS,
        clock: Callable[[], datetime] = utc_now,
        monotonic: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
        write_attempts: int = WRITE_ATTEMPTS,
    ):
        if batch_size < 1:
            raise ValueError("batch_size must be 1 or more")
        self.writer = writer
        self.batch_size = batch_size
        self.batch_seconds = batch_seconds
        self.write_workers = write_workers
        self.clock = clock
        self.monotonic = monotonic
        self.sleep = sleep
        self.write_attempts = write_attempts
        self.seen = RecentIds()
        self.stats: Counter = Counter()
        self.last_message_at = monotonic()
        self._batch: list[Pending] = []
        self._batch_started = 0.0
        self._channel = None

    @staticmethod
    def parse(body: bytes) -> dict:
        """Raise ValueError if the body is not a valid reading batch."""
        message = json.loads(body)
        if not isinstance(message, dict):
            raise ValueError("message is not a JSON object")
        validate(message)
        return message

    def _write(self, item: Pending) -> None:
        for attempt in range(1, self.write_attempts + 1):
            try:
                self.writer.write(item.key, item.body)
                return
            except Exception:
                if attempt == self.write_attempts:
                    raise
                log.warning("write of %s failed (attempt %s/%s), retrying", item.key, attempt, self.write_attempts)
                self.sleep(2 ** (attempt - 1))

    def handle(self, channel, method, properties, body: bytes) -> None:
        """pika callback: one delivery."""
        self._channel = channel
        self.last_message_at = self.monotonic()
        tag = method.delivery_tag
        try:
            message = self.parse(body)
        except ValueError as exc:
            log.error("rejected to readings.dead: %s", str(exc)[:300])
            channel.basic_nack(delivery_tag=tag, requeue=False)
            self.stats["rejected"] += 1
            return

        message_id = message["message_id"]
        if message_id in self.seen or any(p.message_id == message_id for p in self._batch):
            channel.basic_ack(delivery_tag=tag)
            self.stats["redelivered"] += 1
            return

        if not self._batch:
            self._batch_started = self.monotonic()
        key = object_key(message, self.clock())
        self._batch.append(Pending(tag, message_id, len(message["readings"]), key, body))
        if len(self._batch) >= self.batch_size:
            self.flush()

    def flush_if_due(self) -> None:
        if self._batch and self.monotonic() - self._batch_started >= self.batch_seconds:
            self.flush()

    def flush(self) -> None:
        """Write the waiting messages in parallel, then acknowledge them."""
        batch, self._batch = self._batch, []
        if not batch:
            return
        channel = self._channel
        failed: set[int] = set()
        if len(batch) == 1 or self.write_workers <= 1:
            for item in batch:
                try:
                    self._write(item)
                except Exception:
                    log.exception("could not store %s", item.message_id)
                    failed.add(item.tag)
        else:
            with ThreadPoolExecutor(max_workers=min(self.write_workers, len(batch))) as pool:
                futures = {item.tag: pool.submit(self._write, item) for item in batch}
            for item in batch:
                if futures[item.tag].exception() is not None:
                    log.error("could not store %s: %s", item.message_id, futures[item.tag].exception())
                    failed.add(item.tag)

        if not failed:
            # One ACK for the whole batch: every tag up to the last one is now stored (or was already answered).
            channel.basic_ack(delivery_tag=batch[-1].tag, multiple=len(batch) > 1)
        else:
            for item in batch:
                if item.tag in failed:
                    channel.basic_nack(delivery_tag=item.tag, requeue=True)
                else:
                    channel.basic_ack(delivery_tag=item.tag)
        for item in batch:
            if item.tag in failed:
                self.stats["write_failed"] += 1
            else:
                self.seen.add(item.message_id)
                self.stats["stored"] += 1
                self.stats["readings"] += item.readings
        self.stats["batches"] += 1


def configure(channel, consumer: ReadingConsumer, prefetch: int = DEFAULT_PREFETCH) -> None:
    """Prefetch, topology and manual-ACK subscriptions to both queues."""
    if consumer.batch_size > prefetch:
        # With fewer unacknowledged messages allowed than the batch size, a batch would only flush by time.
        consumer.batch_size = prefetch
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
    log.info("consuming %s with prefetch=%s, batches of %s or %ss",
             ", ".join(CONSUMED_QUEUES), prefetch, consumer.batch_size, consumer.batch_seconds)
    last_report = time.monotonic()
    try:
        while True:
            connection.process_data_events(time_limit=min(1.0, consumer.batch_seconds))
            consumer.flush_if_due()
            now = time.monotonic()
            if now - last_report >= report_every:
                log.info("stats: %s", dict(consumer.stats))
                last_report = now
            if exit_when_idle is not None and consumer.monotonic() - consumer.last_message_at >= exit_when_idle:
                log.info("no messages for %ss, exiting", exit_when_idle)
                break
    except KeyboardInterrupt:
        log.info("stopping")
    finally:
        if connection.is_open:
            consumer.flush()  # store and acknowledge what is waiting before closing
            connection.close()
    log.info("done: %s", dict(consumer.stats))
    return consumer.stats

"""F3 consumer: manual ACK only after storing, prefetch, rejects to the dead-letter queue (US-29, T-29.2)."""

import json
import threading
import time
from datetime import datetime, timezone
from types import SimpleNamespace

import pika
import pytest

from ingestion.consumer import ReadingConsumer, configure, run
from ingestion.raw_writer import LocalRawWriter, object_key
from ingestion.topology import CONSUMED_QUEUES, EXCHANGE, LIVE_ROUTING_KEY

STORED_AT = datetime(2026, 11, 2, 14, 5, tzinfo=timezone.utc)


def batch(sequence=1, concentrator="DC-TR-00001", readings=2):
    return {
        "schema_version": "1.0",
        "message_id": f"{concentrator}-{sequence:08d}",
        "concentrator_id": concentrator,
        "sequence": sequence,
        "sent_at": "2013-01-01T00:30:00Z",
        "is_resend": False,
        "readings": [
            {"meter_id": f"MAC{i:06d}", "interval_start": "2013-01-01T00:00:00Z", "energy_kwh": 0.25, "reading_seq": i}
            for i in range(1, readings + 1)
        ],
    }


def body_of(message) -> bytes:
    return json.dumps(message, separators=(",", ":")).encode()


class Log:
    """Shared event log: shows the order of writes and ACKs."""

    def __init__(self):
        self.events = []


class FakeChannel:
    def __init__(self, log):
        self.log = log

    def basic_ack(self, delivery_tag, multiple=False):
        self.log.events.append(("ack", delivery_tag, multiple))

    def basic_nack(self, delivery_tag, multiple=False, requeue=True):
        self.log.events.append(("nack", delivery_tag, requeue))


class FakeWriter:
    def __init__(self, log, fail_times=0):
        self.log = log
        self.fail_times = fail_times
        self.objects = {}

    def write(self, key, body):
        if self.fail_times:
            self.fail_times -= 1
            raise OSError("disk full")
        self.objects[key] = body
        self.log.events.append(("write", key))


def deliver(consumer, channel, body, tag=1):
    consumer.handle(channel, SimpleNamespace(delivery_tag=tag), None, body)


@pytest.fixture
def log():
    return Log()


def make_consumer(writer):
    return ReadingConsumer(writer, batch_size=1, clock=lambda: STORED_AT, sleep=lambda s: None)


def test_object_key_uses_the_storage_time_not_the_reading_time():
    key = object_key(batch(sequence=123), STORED_AT)
    assert key == "source=f3/dataset=readings/ingest_date=2026-11-02/ingest_hour=14/DC-TR-00001_00000123.json"


def test_message_is_acknowledged_only_after_it_is_stored(log):
    writer = FakeWriter(log)
    consumer = make_consumer(writer)
    body = body_of(batch())
    deliver(consumer, FakeChannel(log), body, tag=7)
    key = object_key(batch(), STORED_AT)
    assert log.events == [("write", key), ("ack", 7, False)]
    assert writer.objects[key] == body  # byte for byte
    assert consumer.stats["stored"] == 1 and consumer.stats["readings"] == 2


@pytest.mark.parametrize("body", [b"not json", b"[1, 2]", body_of({"schema_version": "1.0"}), b"\xff\xfe"])
def test_invalid_message_is_rejected_without_requeue_and_never_stored(log, body):
    writer = FakeWriter(log)
    consumer = make_consumer(writer)
    deliver(consumer, FakeChannel(log), body, tag=3)
    assert log.events == [("nack", 3, False)]
    assert writer.objects == {}
    assert consumer.stats["rejected"] == 1


def test_write_is_retried_before_giving_up(log):
    writer = FakeWriter(log, fail_times=2)
    consumer = make_consumer(writer)
    deliver(consumer, FakeChannel(log), body_of(batch()), tag=1)
    assert [e[0] for e in log.events] == ["write", "ack"]


def test_message_that_cannot_be_stored_returns_to_the_queue_without_ack(log):
    writer = FakeWriter(log, fail_times=99)
    consumer = make_consumer(writer)
    deliver(consumer, FakeChannel(log), body_of(batch()), tag=4)
    assert log.events == [("nack", 4, True)]
    assert consumer.stats["write_failed"] == 1


def test_exact_redelivery_is_acknowledged_without_writing_twice(log):
    writer = FakeWriter(log)
    consumer = make_consumer(writer)
    channel = FakeChannel(log)
    deliver(consumer, channel, body_of(batch()), tag=1)
    deliver(consumer, channel, body_of(batch()), tag=2)
    assert [e[0] for e in log.events] == ["write", "ack", "ack"]
    assert consumer.stats["redelivered"] == 1


def test_configure_sets_prefetch_and_manual_ack_on_both_queues():
    calls = []

    class Channel:
        def basic_qos(self, prefetch_count):
            calls.append(("qos", prefetch_count))

        def exchange_declare(self, **kw):
            pass

        def queue_declare(self, **kw):
            pass

        def queue_bind(self, **kw):
            pass

        def basic_consume(self, queue, on_message_callback, auto_ack):
            calls.append(("consume", queue, auto_ack))

    configure(Channel(), make_consumer(None), prefetch=50)
    assert calls[0] == ("qos", 50)
    assert [(q, a) for _, q, a in calls[1:]] == [(q, False) for q in CONSUMED_QUEUES]


def test_local_writer_leaves_no_temporary_files(tmp_path):
    writer = LocalRawWriter(tmp_path)
    writer.write("source=f3/dataset=readings/ingest_date=2026-11-02/ingest_hour=14/x.json", b"{}")
    files = [p.name for p in tmp_path.rglob("*") if p.is_file()]
    assert files == ["x.json"]


# ---------- against a real RabbitMQ (skipped without RABBITMQ_TEST_URL) ----------

def test_consumer_stores_every_published_message_and_empties_the_queues(rabbitmq_url, tmp_path):
    connection = pika.BlockingConnection(pika.URLParameters(rabbitmq_url))
    channel = connection.channel()
    from ingestion.topology import declare_topology

    declare_topology(channel)
    for seq in range(1, 21):
        channel.basic_publish(EXCHANGE, LIVE_ROUTING_KEY, body_of(batch(sequence=seq)))
    consumer = ReadingConsumer(LocalRawWriter(tmp_path))
    stats = run(rabbitmq_url, consumer, prefetch=5, exit_when_idle=2)
    assert stats["stored"] == 20
    assert len(list(tmp_path.rglob("*.json"))) == 20
    for queue in CONSUMED_QUEUES:
        assert channel.queue_declare(queue=queue, passive=True).method.message_count == 0
    connection.close()


def test_consumer_stops_after_the_idle_time(rabbitmq_url, tmp_path):
    consumer = ReadingConsumer(LocalRawWriter(tmp_path))
    started = time.monotonic()
    worker = threading.Thread(target=run, args=(rabbitmq_url, consumer), kwargs={"exit_when_idle": 1})
    worker.start()
    worker.join(timeout=15)
    assert not worker.is_alive()
    assert time.monotonic() - started < 15

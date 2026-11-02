"""Batch writes to raw (US-29, T-29.3): write N messages, then one ACK; flush by size, by time and on stop."""

import json
from datetime import datetime, timezone
from types import SimpleNamespace

import pika

from ingestion.consumer import ReadingConsumer, configure, run
from ingestion.raw_writer import S3RawWriter
from ingestion.topology import CONSUMED_QUEUES, EXCHANGE, RESEND_ROUTING_KEY, declare_topology

STORED_AT = datetime(2026, 11, 2, 14, 5, tzinfo=timezone.utc)


def body(sequence):
    return json.dumps({
        "schema_version": "1.0",
        "message_id": f"DC-TR-00001-{sequence:08d}",
        "concentrator_id": "DC-TR-00001",
        "sequence": sequence,
        "sent_at": "2013-01-01T00:30:00Z",
        "is_resend": True,
        "readings": [{"meter_id": "MAC000001", "interval_start": "2013-01-01T00:00:00Z",
                      "energy_kwh": 0.2, "reading_seq": sequence}],
    }).encode()


class Recorder:
    def __init__(self, fail_keys=()):
        self.events = []
        self.fail_keys = set(fail_keys)

    # channel
    def basic_ack(self, delivery_tag, multiple=False):
        self.events.append(("ack", delivery_tag, multiple))

    def basic_nack(self, delivery_tag, multiple=False, requeue=True):
        self.events.append(("nack", delivery_tag, requeue))

    # writer
    def write(self, key, body):
        if any(key.endswith(k) for k in self.fail_keys):
            raise OSError("S3 unavailable")
        self.events.append(("write", key.rsplit("/", 1)[-1]))


class Clock:
    def __init__(self):
        self.now = 1000.0

    def __call__(self):
        return self.now


def consumer_for(rec, clock=None, **kw):
    return ReadingConsumer(rec, clock=lambda: STORED_AT, monotonic=clock or Clock(), sleep=lambda s: None,
                           write_workers=1, **kw)


def deliver(consumer, rec, sequence, tag):
    consumer.handle(rec, SimpleNamespace(delivery_tag=tag), None, body(sequence))


def test_nothing_is_written_or_acknowledged_until_the_batch_is_full():
    rec = Recorder()
    consumer = consumer_for(rec, batch_size=3)
    deliver(consumer, rec, 1, tag=1)
    deliver(consumer, rec, 2, tag=2)
    assert rec.events == []
    deliver(consumer, rec, 3, tag=3)
    assert rec.events == [
        ("write", "DC-TR-00001_00000001.json"),
        ("write", "DC-TR-00001_00000002.json"),
        ("write", "DC-TR-00001_00000003.json"),
        ("ack", 3, True),  # one ACK for the three
    ]
    assert consumer.stats["batches"] == 1 and consumer.stats["stored"] == 3


def test_an_incomplete_batch_is_written_when_its_time_is_up():
    rec, clock = Recorder(), Clock()
    consumer = consumer_for(rec, clock, batch_size=50, batch_seconds=2)
    deliver(consumer, rec, 1, tag=1)
    clock.now += 1.9
    consumer.flush_if_due()
    assert rec.events == []
    clock.now += 0.2
    consumer.flush_if_due()
    assert rec.events == [("write", "DC-TR-00001_00000001.json"), ("ack", 1, False)]


def test_when_one_write_fails_only_that_message_returns_to_the_queue():
    rec = Recorder(fail_keys=["_00000002.json"])
    consumer = consumer_for(rec, batch_size=3)
    for seq in (1, 2, 3):
        deliver(consumer, rec, seq, tag=seq)
    acks = [e for e in rec.events if e[0] in ("ack", "nack")]
    assert acks == [("ack", 1, False), ("nack", 2, True), ("ack", 3, False)]
    assert consumer.stats["stored"] == 2 and consumer.stats["write_failed"] == 1


def test_an_invalid_message_is_rejected_at_once_and_does_not_join_the_batch():
    rec = Recorder()
    consumer = consumer_for(rec, batch_size=2)
    deliver(consumer, rec, 1, tag=1)
    consumer.handle(rec, SimpleNamespace(delivery_tag=2), None, b"garbage")
    deliver(consumer, rec, 3, tag=3)
    assert rec.events[0] == ("nack", 2, False)
    assert rec.events[-1] == ("ack", 3, True)


def test_a_redelivery_waiting_in_the_same_batch_is_not_written_twice():
    rec = Recorder()
    consumer = consumer_for(rec, batch_size=2)
    deliver(consumer, rec, 1, tag=1)
    deliver(consumer, rec, 1, tag=2)
    assert rec.events == [("ack", 2, False)]
    deliver(consumer, rec, 2, tag=3)
    assert [e[0] for e in rec.events].count("write") == 2


def test_batches_are_written_in_parallel_threads():
    rec = Recorder()
    consumer = ReadingConsumer(rec, batch_size=10, clock=lambda: STORED_AT, write_workers=4)
    for seq in range(1, 11):
        deliver(consumer, rec, seq, tag=seq)
    assert sorted(e[1] for e in rec.events if e[0] == "write") == [f"DC-TR-00001_{s:08d}.json" for s in range(1, 11)]
    assert rec.events[-1] == ("ack", 10, True)


def test_batch_size_never_exceeds_prefetch():
    class Channel:
        def __getattr__(self, name):
            return lambda *a, **k: None

    consumer = consumer_for(Recorder(), batch_size=500)
    configure(Channel(), consumer, prefetch=100)
    assert consumer.batch_size == 100


def test_s3_writer_puts_the_body_unchanged_under_the_key():
    class FakeS3:
        def __init__(self):
            self.calls = []

        def put_object(self, **kw):
            self.calls.append(kw)

    s3 = FakeS3()
    S3RawWriter("voltiagrid-dev-raw-123", client=s3).write("source=f3/k.json", b'{"a":1}')
    assert s3.calls == [{"Bucket": "voltiagrid-dev-raw-123", "Key": "source=f3/k.json", "Body": b'{"a":1}',
                         "ContentType": "application/json"}]


# ---------- against a real RabbitMQ (skipped without RABBITMQ_TEST_URL) ----------

def test_a_resend_of_500_messages_is_stored_in_batches_and_the_queues_end_empty(rabbitmq_url, tmp_path):
    from ingestion.raw_writer import LocalRawWriter

    connection = pika.BlockingConnection(pika.URLParameters(rabbitmq_url))
    channel = connection.channel()
    declare_topology(channel)
    for seq in range(1, 501):
        channel.basic_publish(EXCHANGE, RESEND_ROUTING_KEY, body(seq))
    consumer = ReadingConsumer(LocalRawWriter(tmp_path), batch_size=50, batch_seconds=1)
    stats = run(rabbitmq_url, consumer, prefetch=100, exit_when_idle=3)
    assert stats["stored"] == 500
    assert stats["batches"] >= 10
    assert len(list(tmp_path.rglob("*.json"))) == 500
    for queue in CONSUMED_QUEUES:
        assert channel.queue_declare(queue=queue, passive=True).method.message_count == 0
    connection.close()

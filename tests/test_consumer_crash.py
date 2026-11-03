"""The consumer crashes and no reading is lost (US-29, T-29.4). Needs RABBITMQ_TEST_URL (the CI starts a RabbitMQ).

Each test publishes a resend, kills a consumer like `kill -9` at a chosen point (tests/crash_consumer.py), starts
a healthy consumer and checks that every message is in raw, the reading queues are empty and nothing was lost.
"""

import json
import subprocess
import sys
import time
from pathlib import Path

import pika
import pytest

from ingestion.consumer import ReadingConsumer, run
from ingestion.raw_writer import LocalRawWriter
from ingestion.topology import (
    CONSUMED_QUEUES,
    DEAD_LETTER_QUEUE,
    DELIVERY_LIMIT,
    EXCHANGE,
    RESEND_ROUTING_KEY,
    declare_topology,
)

ROOT = Path(__file__).resolve().parents[1]
CRASH_EXIT_CODE = 3


def message(sequence, meters=4):
    return {
        "schema_version": "1.0",
        "message_id": f"DC-TR-00007-{sequence:08d}",
        "concentrator_id": "DC-TR-00007",
        "sequence": sequence,
        "sent_at": "2013-01-02T00:00:00Z",
        "is_resend": True,
        "readings": [
            {"meter_id": f"MAC{m:06d}", "interval_start": "2013-01-01T00:00:00Z", "energy_kwh": 0.3,
             "reading_seq": sequence * 10 + m}
            for m in range(meters)
        ],
    }


@pytest.fixture
def broker(rabbitmq_url):
    connection = pika.BlockingConnection(pika.URLParameters(rabbitmq_url))
    channel = connection.channel()
    declare_topology(channel)
    yield rabbitmq_url, channel
    connection.close()


def publish(channel, sequences):
    for seq in sequences:
        channel.basic_publish(EXCHANGE, RESEND_ROUTING_KEY, json.dumps(message(seq)).encode(),
                              properties=pika.BasicProperties(delivery_mode=2))


def crash(url, raw_dir, *args):
    result = subprocess.run([sys.executable, "-m", "tests.crash_consumer", url, str(raw_dir), *args],
                            cwd=ROOT, capture_output=True, text=True, timeout=60)
    return result.returncode


def drain(url, raw_dir):
    return run(url, ReadingConsumer(LocalRawWriter(raw_dir), batch_size=20, batch_seconds=1), prefetch=50,
               exit_when_idle=3)


def stored_ids(raw_dir):
    return [json.loads(p.read_bytes())["message_id"] for p in Path(raw_dir).rglob("*.json")]


def depth(channel, queue):
    return channel.queue_declare(queue=queue, passive=True).method.message_count


def depth_becomes(channel, queue, expected, timeout=10.0):
    """RabbitMQ returns the unacknowledged messages a moment after it sees the connection drop."""
    deadline = time.monotonic() + timeout
    while depth(channel, queue) != expected and time.monotonic() < deadline:
        time.sleep(0.2)
    return depth(channel, queue)


def test_crash_in_the_middle_of_a_batch_loses_nothing(broker, tmp_path):
    url, channel = broker
    publish(channel, range(1, 201))
    # batch of 20: the first batch is written and acknowledged, the second dies after 10 writes, before its ACK
    assert crash(url, tmp_path, "--after-writes", "30") == CRASH_EXIT_CODE
    assert len(set(stored_ids(tmp_path))) == 30
    assert depth_becomes(channel, "readings.resend", 180) == 180  # 200 - 20 acknowledged: the rest came back

    drain(url, tmp_path)
    ids = set(stored_ids(tmp_path))
    assert ids == {f"DC-TR-00007-{s:08d}" for s in range(1, 201)}
    assert all(depth(channel, q) == 0 for q in CONSUMED_QUEUES)
    assert depth(channel, DEAD_LETTER_QUEUE) == 0


def test_crash_before_the_first_write_returns_every_message(broker, tmp_path):
    url, channel = broker
    publish(channel, range(1, 51))
    assert crash(url, tmp_path, "--after-writes", "0") == CRASH_EXIT_CODE
    assert stored_ids(tmp_path) == []
    assert depth_becomes(channel, "readings.resend", 50) == 50

    stats = drain(url, tmp_path)
    assert stats["stored"] == 50
    assert len(set(stored_ids(tmp_path))) == 50


def test_three_crashes_in_a_row_still_lose_nothing(broker, tmp_path):
    url, channel = broker
    publish(channel, range(1, 301))
    for _ in range(3):
        assert crash(url, tmp_path, "--after-writes", "45") == CRASH_EXIT_CODE
    drain(url, tmp_path)
    assert set(stored_ids(tmp_path)) == {f"DC-TR-00007-{s:08d}" for s in range(1, 301)}
    assert all(depth(channel, q) == 0 for q in CONSUMED_QUEUES)


def test_message_that_crashes_the_consumer_every_time_ends_in_the_dead_letter_queue(broker, tmp_path):
    url, channel = broker
    poison = "DC-TR-00007-00000001"
    publish(channel, range(1, 11))
    crashes = 0
    # prefetch 1 and batch 1: when it crashes, the poison message is the only one not acknowledged
    while crashes <= DELIVERY_LIMIT + 2:
        code = crash(url, tmp_path, "--on-message", poison, "--batch-size", "1", "--prefetch", "1")
        if code != CRASH_EXIT_CODE:
            break  # the poison message is gone: this consumer stored the other nine and stopped when idle
        crashes += 1
    # every crash counts as a delivery; after DELIVERY_LIMIT of them RabbitMQ dead-letters the message
    assert DELIVERY_LIMIT <= crashes <= DELIVERY_LIMIT + 1
    drain(url, tmp_path)

    method, _, body = channel.basic_get(queue=DEAD_LETTER_QUEUE, auto_ack=True)
    assert json.loads(body)["message_id"] == poison
    assert depth(channel, DEAD_LETTER_QUEUE) == 0
    assert set(stored_ids(tmp_path)) == {f"DC-TR-00007-{s:08d}" for s in range(2, 11)}

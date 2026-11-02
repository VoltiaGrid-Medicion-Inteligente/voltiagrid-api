"""RabbitMQ topology of F3 (US-29, T-29.1)."""

import json
import time

import pika
import pytest

from ingestion.topology import (
    BINDINGS,
    DEAD_LETTER_EXCHANGE,
    DEAD_LETTER_QUEUE,
    DELIVERY_LIMIT,
    EXCHANGE,
    LIVE_QUEUE,
    LIVE_ROUTING_KEY,
    RESEND_QUEUE,
    RESEND_ROUTING_KEY,
    declare_topology,
)


class RecordingChannel:
    def __init__(self):
        self.exchanges, self.queues, self.bindings = {}, {}, []

    def exchange_declare(self, exchange, exchange_type, durable):
        self.exchanges[exchange] = (exchange_type, durable)

    def queue_declare(self, queue, durable, arguments=None):
        self.queues[queue] = (durable, arguments or {})

    def queue_bind(self, queue, exchange, routing_key=None):
        self.bindings.append((exchange, routing_key, queue))


@pytest.fixture
def declared():
    channel = RecordingChannel()
    declare_topology(channel)
    return channel


def test_exchanges_are_durable_topic_and_fanout(declared):
    assert declared.exchanges[EXCHANGE] == ("topic", True)
    assert declared.exchanges[DEAD_LETTER_EXCHANGE] == ("fanout", True)


def test_each_routing_key_feeds_its_own_queue(declared):
    assert (EXCHANGE, LIVE_ROUTING_KEY, LIVE_QUEUE) in declared.bindings
    assert (EXCHANGE, RESEND_ROUTING_KEY, RESEND_QUEUE) in declared.bindings
    assert (DEAD_LETTER_EXCHANGE, None, DEAD_LETTER_QUEUE) in declared.bindings


def test_reading_queues_are_durable_quorum_with_dead_letters_and_delivery_limit(declared):
    for queue in BINDINGS:
        durable, args = declared.queues[queue]
        assert durable is True
        assert args["x-queue-type"] == "quorum"
        assert args["x-dead-letter-exchange"] == DEAD_LETTER_EXCHANGE
        assert args["x-delivery-limit"] == DELIVERY_LIMIT


def test_dead_letter_queue_is_durable_and_has_no_dead_letter_of_its_own(declared):
    durable, args = declared.queues[DEAD_LETTER_QUEUE]
    assert durable is True
    assert "x-dead-letter-exchange" not in args


def test_simulator_uses_the_same_routing_keys():
    from simulators.concentrator import generator

    assert generator.LIVE_ROUTING_KEY == LIVE_ROUTING_KEY
    assert generator.RESEND_ROUTING_KEY == RESEND_ROUTING_KEY


# ---------- against a real RabbitMQ (skipped without RABBITMQ_TEST_URL) ----------

def _channel(url):
    connection = pika.BlockingConnection(pika.URLParameters(url))
    return connection, connection.channel()


def _get(channel, queue, timeout=5.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        method, _, body = channel.basic_get(queue=queue, auto_ack=False)
        if method:
            return method, body
        time.sleep(0.1)
    return None, None


def test_declaring_twice_is_idempotent_and_routing_works(rabbitmq_url):
    connection, channel = _channel(rabbitmq_url)
    declare_topology(channel)
    declare_topology(channel)
    channel.basic_publish(EXCHANGE, RESEND_ROUTING_KEY, b'{"n": 1}')
    method, body = _get(channel, RESEND_QUEUE)
    assert json.loads(body) == {"n": 1}
    channel.basic_ack(method.delivery_tag)
    assert channel.queue_declare(queue=LIVE_QUEUE, passive=True).method.message_count == 0
    connection.close()


def test_rejected_message_goes_to_the_dead_letter_queue(rabbitmq_url):
    connection, channel = _channel(rabbitmq_url)
    declare_topology(channel)
    channel.basic_publish(EXCHANGE, LIVE_ROUTING_KEY, b"not json")
    method, _ = _get(channel, LIVE_QUEUE)
    channel.basic_nack(method.delivery_tag, requeue=False)
    _, body = _get(channel, DEAD_LETTER_QUEUE)
    assert body == b"not json"
    connection.close()


def test_message_never_acked_goes_to_the_dead_letter_queue_after_the_delivery_limit(rabbitmq_url):
    connection, channel = _channel(rabbitmq_url)
    declare_topology(channel)
    channel.basic_publish(EXCHANGE, LIVE_ROUTING_KEY, b'{"poison": true}')
    for _ in range(DELIVERY_LIMIT + 1):
        method, _ = _get(channel, LIVE_QUEUE)
        assert method is not None
        channel.basic_nack(method.delivery_tag, requeue=True)
    _, body = _get(channel, DEAD_LETTER_QUEUE)
    assert body == b'{"poison": true}'
    assert channel.queue_declare(queue=LIVE_QUEUE, passive=True).method.message_count == 0
    connection.close()

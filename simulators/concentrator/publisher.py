import json
import logging
import time
from typing import Protocol

import pika
from pika.exceptions import AMQPConnectionError

log = logging.getLogger(__name__)

EXCHANGE = "readings"
DEAD_LETTER_EXCHANGE = "readings.dlx"
DEAD_LETTER_QUEUE = "readings.dead"
QUEUES = {"readings.live": "readings.live", "readings.resend": "readings.resend"}


class Publisher(Protocol):
    def publish(self, routing_key: str, message: dict) -> None: ...

    def close(self) -> None: ...


class MemoryPublisher:
    def __init__(self):
        self.sent: list[tuple[str, dict]] = []

    def publish(self, routing_key: str, message: dict) -> None:
        self.sent.append((routing_key, message))

    def close(self) -> None:
        pass


def declare_topology(channel) -> None:
    channel.exchange_declare(exchange=EXCHANGE, exchange_type="topic", durable=True)
    channel.exchange_declare(exchange=DEAD_LETTER_EXCHANGE, exchange_type="fanout", durable=True)
    channel.queue_declare(queue=DEAD_LETTER_QUEUE, durable=True)
    channel.queue_bind(queue=DEAD_LETTER_QUEUE, exchange=DEAD_LETTER_EXCHANGE)
    for queue, routing_key in QUEUES.items():
        channel.queue_declare(
            queue=queue,
            durable=True,
            arguments={"x-dead-letter-exchange": DEAD_LETTER_EXCHANGE},
        )
        channel.queue_bind(queue=queue, exchange=EXCHANGE, routing_key=routing_key)


def message_properties(message: dict) -> pika.BasicProperties:
    return pika.BasicProperties(
        content_type="application/json",
        delivery_mode=pika.DeliveryMode.Persistent,
        message_id=message["message_id"],
        headers={"schema_version": message["schema_version"], "is_resend": message["is_resend"]},
    )


class RabbitPublisher:
    def __init__(self, url: str, attempts: int = 10, wait_seconds: float = 3.0):
        self._connection = self._connect(url, attempts, wait_seconds)
        self._channel = self._connection.channel()
        self._channel.confirm_delivery()
        declare_topology(self._channel)

    @staticmethod
    def _connect(url: str, attempts: int, wait_seconds: float):
        for attempt in range(1, attempts + 1):
            try:
                return pika.BlockingConnection(pika.URLParameters(url))
            except AMQPConnectionError:
                if attempt == attempts:
                    raise
                log.warning("RabbitMQ not ready (attempt %s/%s), retrying...", attempt, attempts)
                time.sleep(wait_seconds)

    def publish(self, routing_key: str, message: dict) -> None:
        self._channel.basic_publish(
            exchange=EXCHANGE,
            routing_key=routing_key,
            body=json.dumps(message, separators=(",", ":")).encode(),
            properties=message_properties(message),
            mandatory=True,
        )

    def close(self) -> None:
        if self._connection.is_open:
            self._connection.close()
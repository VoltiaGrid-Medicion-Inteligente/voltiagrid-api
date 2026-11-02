import json
import logging
import time
from typing import Protocol

import pika
from pika.exceptions import AMQPConnectionError

from ingestion.topology import EXCHANGE, declare_topology

log = logging.getLogger(__name__)


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
"""RabbitMQ topology for F3 readings (US-29, T-29.1). Single source for the publisher and the consumer.

    concentrator --readings.live----> [readings] topic --> readings.live   (quorum) --+
    concentrator --readings.resend--> [readings] topic --> readings.resend (quorum) --+--> consumer --> S3 raw
                                                                                       |
                rejected, or delivered DELIVERY_LIMIT times without an ACK  -----------+--> [readings.dlx] fanout --> readings.dead

- Every queue is a quorum queue: replicated on disk, survives broker restarts, and counts deliveries.
- A message that is delivered DELIVERY_LIMIT times without an ACK (the consumer crashes or fails to store it
  every time) goes to readings.dead instead of looping forever.
- A message the consumer cannot parse is rejected without requeue and also goes to readings.dead.
"""

EXCHANGE = "readings"
EXCHANGE_TYPE = "topic"
DEAD_LETTER_EXCHANGE = "readings.dlx"
DEAD_LETTER_QUEUE = "readings.dead"

LIVE_ROUTING_KEY = "readings.live"
RESEND_ROUTING_KEY = "readings.resend"
LIVE_QUEUE = "readings.live"
RESEND_QUEUE = "readings.resend"

# queue -> routing key that feeds it
BINDINGS = {LIVE_QUEUE: LIVE_ROUTING_KEY, RESEND_QUEUE: RESEND_ROUTING_KEY}
CONSUMED_QUEUES = (LIVE_QUEUE, RESEND_QUEUE)

DELIVERY_LIMIT = 5


def queue_arguments() -> dict:
    """Arguments of the two reading queues. Changing them needs the old queues deleted first (see docs/INGESTION.md)."""
    return {
        "x-queue-type": "quorum",
        "x-dead-letter-exchange": DEAD_LETTER_EXCHANGE,
        "x-delivery-limit": DELIVERY_LIMIT,
    }


def dead_letter_arguments() -> dict:
    return {"x-queue-type": "quorum"}


def declare_topology(channel) -> None:
    """Idempotent: publisher and consumer both call it at startup, whichever starts first creates everything."""
    channel.exchange_declare(exchange=EXCHANGE, exchange_type=EXCHANGE_TYPE, durable=True)
    channel.exchange_declare(exchange=DEAD_LETTER_EXCHANGE, exchange_type="fanout", durable=True)
    channel.queue_declare(queue=DEAD_LETTER_QUEUE, durable=True, arguments=dead_letter_arguments())
    channel.queue_bind(queue=DEAD_LETTER_QUEUE, exchange=DEAD_LETTER_EXCHANGE)
    for queue, routing_key in BINDINGS.items():
        channel.queue_declare(queue=queue, durable=True, arguments=queue_arguments())
        channel.queue_bind(queue=queue, exchange=EXCHANGE, routing_key=routing_key)

# F3 ingestion: RabbitMQ to S3 raw (US-29)

Concentrators (F3) publish one message per transformer every 30 minutes. Not a single reading can be lost
(RNF-03, ADR-001), so every step keeps the message until the next step has it safe.

## Topology (T-29.1)

Declared in `ingestion/topology.py`. The simulator and the consumer both call `declare_topology` at startup, so it
does not matter which one starts first.

```
concentrator --readings.live----> [readings] topic --> readings.live   (quorum) --+
concentrator --readings.resend--> [readings] topic --> readings.resend (quorum) --+--> consumer --> S3 raw
                                                                                   |
     rejected, or delivered 5 times without an ACK  --------------------------------+--> [readings.dlx] fanout --> readings.dead
```

| Object | Type | Why |
|---|---|---|
| `readings` | topic exchange, durable | Concentrators publish here with a routing key; they never write to a queue directly. |
| `readings.live` | quorum queue, routing key `readings.live` | Normal traffic every 30 minutes. |
| `readings.resend` | quorum queue, routing key `readings.resend` | Bulk resends after an outage (CA-08). Separate so a long resend never delays live readings and so its depth shows how far behind the resend is. |
| `readings.dlx` | fanout exchange, durable | Receives every dead letter from both queues. |
| `readings.dead` | quorum queue | Messages to inspect by hand: rejected by the consumer (not valid JSON or not the contract) or delivered 5 times without an ACK. |

Queue arguments of `readings.live` and `readings.resend`:

| Argument | Value | Effect |
|---|---|---|
| `x-queue-type` | `quorum` | Replicated on disk; survives a broker restart; counts how many times each message was delivered. |
| `x-dead-letter-exchange` | `readings.dlx` | Where rejected and over-delivered messages go. |
| `x-delivery-limit` | `5` | After 5 deliveries without an ACK (the consumer crashed or failed to store it each time) the message goes to `readings.dead` instead of looping forever. |

Publishing rules (unchanged from US-11): persistent messages, publisher confirms and `mandatory=True`, so a message
that no queue accepts comes back to the publisher as an error instead of disappearing.

### Changing the topology on an existing broker

RabbitMQ does not change the arguments of an existing queue: declaring it with different arguments fails with
`PRECONDITION_FAILED`. Before the first run with this version, delete the old classic queues once:

```powershell
docker compose stop f3-simulator
docker compose exec rabbitmq rabbitmqctl delete_queue readings.live
docker compose exec rabbitmq rabbitmqctl delete_queue readings.resend
docker compose exec rabbitmq rabbitmqctl delete_queue readings.dead
docker compose up -d --build f3-simulator
```

(Or delete `readings.live`, `readings.resend` and `readings.dead` in the console, http://localhost:15672 → **Queues**.)
Any reading still waiting in those queues is lost, so do it in a local stack, never with data you need.

### Tests

`tests/test_ingestion_topology.py` checks the declarations with a fake channel. Three more tests run against a real
RabbitMQ when `RABBITMQ_TEST_URL` is set (the CI starts one): declaring twice is harmless, a rejected message reaches
`readings.dead`, and a message never acknowledged reaches `readings.dead` after the delivery limit. The fixture
deletes the queues before and after each test, which is why it never uses `RABBITMQ_URL` from `.env`.

## Consumer (T-29.2)

`ingestion/consumer.py`, run with `python -m ingestion` or as the `f3-consumer` service of `docker-compose.yml`.

| Rule | How |
|---|---|
| ACK only after the message is in raw | `basic_ack` is called after the write returns. If the consumer dies before, RabbitMQ delivers the message again. |
| Prefetch | `basic_qos(prefetch_count=CONSUMER_PREFETCH)`, default 100: one consumer never holds more than 100 unacknowledged messages, so a crash returns at most 100 and a long resend is shared between consumers. |
| Invalid message | Not JSON or not the contract (`reading_batch.v1.json`): `basic_nack(requeue=False)`, it goes to `readings.dead` and does not block the queue. |
| Storage fails | 3 attempts (1 s and 2 s apart), then `basic_nack(requeue=True)`. After 5 deliveries RabbitMQ moves it to `readings.dead`. |
| Exact redelivery | Same `message_id` already stored by this process: ACK without writing again. After a restart a second copy can land in raw; Spark removes exact duplicates (meter, interval, sequence) before clean. |

Each message is stored byte for byte under the key of the *Data lake layout* page:

```
source=f3/dataset=readings/ingest_date=YYYY-MM-DD/ingest_hour=HH/<concentrator>_<sequence>.json
```

`ingest_date` and `ingest_hour` are the UTC time it was stored, so a resend of old readings never overwrites anything
(ADR-007). Locally the raw bucket is the folder `lake/raw` of this repo (`LAKE_DIR` in `.env`, ignored by git).

| Variable | Default | Meaning |
|---|---|---|
| `RABBITMQ_URL` | from `.env` | Broker |
| `RAW_DIR` | `lake/raw` (`/lake/raw` in the container) | Folder that plays the raw bucket |
| `CONSUMER_PREFETCH` | `100` | Unacknowledged messages per consumer |
| `RAW_BATCH_SIZE` | `50` | Messages written together before one ACK (never more than the prefetch) |
| `RAW_BATCH_SECONDS` | `2` | Longest time a message waits for its batch to fill |
| `RAW_BUCKET` | empty | In AWS: the raw bucket. When set, `RAW_DIR` is ignored and objects go to S3 |

```powershell
docker compose up -d --build f3-consumer
docker compose logs -f f3-consumer          # "stats: {'stored': ..., 'readings': ...}" every minute
python -m ingestion --exit-when-idle 30     # from the terminal: drain the queues and stop
```

## Batch writes (T-29.3)

Writing and acknowledging one message at a time makes a 48,000-reading resend wait on 1,000 round trips to S3. The
consumer groups them instead:

1. Each valid message waits in memory, **unacknowledged**, until there are `RAW_BATCH_SIZE` of them or the oldest
   waited `RAW_BATCH_SECONDS`.
2. The batch is written in parallel (8 threads; each object is still its own file, with the key above).
3. When every write succeeded, a single `basic_ack(multiple=True)` on the last delivery tag acknowledges the whole
   batch. If some writes failed, the stored ones are acknowledged one by one and the failed ones go back to the queue
   with `basic_nack(requeue=True)`.

Why nothing is lost: a message is acknowledged only after its own write returned. If the consumer dies with a batch
in memory, those messages were never acknowledged and RabbitMQ delivers them again. On `docker compose stop`
(SIGTERM) the consumer writes and acknowledges the batch it holds before closing.

The batch can never be bigger than the prefetch: with fewer unacknowledged messages allowed than the batch size,
RabbitMQ would stop delivering and the batch would only flush by time. `configure` lowers the batch size if needed.

In AWS the same code writes to S3 when `RAW_BUCKET` is set (`S3RawWriter`, `boto3`). The task role needs only
`s3:PutObject` on the raw bucket (policy `datalake-ingest`, no delete).

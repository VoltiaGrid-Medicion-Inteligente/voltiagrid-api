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

## Crash tests (T-29.4)

`tests/test_consumer_crash.py` runs against a real RabbitMQ (the CI starts one; locally set `RABBITMQ_TEST_URL`). A
helper consumer (`tests/crash_consumer.py`) dies with `os._exit`, like `kill -9`: no flush, no ACK, no clean close.
Then a healthy consumer drains the queues.

| Test | Crash point | What it proves |
|---|---|---|
| `test_crash_in_the_middle_of_a_batch_loses_nothing` | 200 messages, batches of 20: the first batch is written and acknowledged, the second dies after 10 writes | The 180 unacknowledged messages return to the queue; after the restart all 200 are in raw and the queues are empty. The 10 written twice land on the same key. |
| `test_crash_before_the_first_write_returns_every_message` | Before any write, with 50 messages in its prefetch | All 50 return; the next consumer stores them. |
| `test_three_crashes_in_a_row_still_lose_nothing` | Three consumers die one after another, 300 messages | All 300 end in raw. |
| `test_message_that_crashes_the_consumer_every_time_ends_in_the_dead_letter_queue` | A message that kills the consumer every time it arrives | After the delivery limit RabbitMQ moves it to `readings.dead`; the other 9 messages are stored. The queue does not get stuck. |

Every crash counts as a delivery for the quorum queue, so a normal message survives up to 5 crashes in a row while
it is in a consumer's prefetch; the dead-letter queue is checked by hand after any incident.

### Manual check with the stack (evidence for the PR)

```powershell
docker compose up -d --build rabbitmq f3-consumer
docker compose stop f3-consumer
python -m simulators.concentrator --no-db --meters 1000 --outage-meters 1000 --outage-hours 24 --ticks 49 --tick-seconds 0
docker compose start f3-consumer
Start-Sleep -Seconds 2
docker compose kill f3-consumer          # like pulling the plug, in the middle of the resend
docker compose start f3-consumer
docker compose logs --tail 5 f3-consumer
(Get-ChildItem lake/raw -Recurse -Filter *.json).Count
```

Expected: the queues in http://localhost:15672 end at 0 messages, `readings.dead` is empty, and there are **784**
files: the simulator's last interval line says `784 messages (768 resent), 47906 readings` (16 concentrators: 48 held
messages each plus the live one). Reference run without the kill: `done: {'stored': 784, 'readings': 47906, ...}`.

## Draining a resend and scaling (US-31, T-31.2)

CA-08: after a 24-hour outage, 1,000 meters resend everything at once. With the simulator that is 768 resent
messages plus 16 live ones, 47,906 readings (16 concentrators × 49 intervals; gaps and missing days make it a bit
less than 48,000). `scripts/measure_drain.py` measures how long the consumers take to empty `readings.resend`.

### How to measure (three terminals in the repo folder)

```powershell
# 1. Stack up and consumers stopped, so the resend waits in the queue
docker compose up -d --build rabbitmq f3-consumer
docker compose stop f3-consumer

# 2. Publish the outage and the resend (about 10 s)
python -m simulators.concentrator --no-db --meters 1000 --outage-meters 1000 --outage-hours 24 --ticks 49 --tick-seconds 0

# 3. Terminal 2: start watching the queue
python -m scripts.measure_drain --readings 47906 --csv drain-1.csv

# 4. Terminal 1: start N consumers (1, then repeat steps 2 to 4 with 2 and 3)
docker compose up -d --scale f3-consumer=1 f3-consumer
```

`measure_drain` prints the depth every second and ends with
`peak 768 messages, drained in X s, Y messages/s, Z readings/s`. Between runs, `docker compose stop f3-consumer`
again before publishing.

### Results

Reference run (Linux laptop, RabbitMQ 3.12, consumers as local processes writing to a local disk, batches of 50,
prefetch 100). The time includes starting the consumers, about 1 s:

| Consumers | Drain time | Messages/s | Readings/s |
|---|---|---|---|
| 1 | 4.0 s | 191 | 11,887 |
| 2 | 1.8 s | 436 | 27,219 |
| 3 | 1.5 s | 509 | 31,726 |

With the Docker stack on the team laptop (Docker Desktop, `lake/` mounted from Windows):

| Consumers | Drain time | Messages/s | Readings/s | Laptop |
|---|---|---|---|---|
| 1 | 29.3 s | 26.2 | 1,633 | Intel Core i5-6300U (2 cores), 8 GB RAM, RabbitMQ 3.13 |
| 2 | 24.8 s | 30.9 | 1,929 | |
| 3 | 93.1 s | 8.3 | 515 | |

After each run: `readings.resend` and `readings.dead` at 0 in the console, and
`(Get-ChildItem lake/raw -Recurse -Filter *.json).Count` equals 784.

All three runs ended with 784 files and `readings.live`, `readings.resend` and `readings.dead` at 0: nothing was lost
or dead-lettered. On this laptop more consumers did not help: two were a little faster than one, and three were the
slowest (the last 64 messages waited about 40 s). The three consumers shared the work (282 + 262 + 240 = 784 stored)
with no errors in their logs; the time went into writing to the Windows bind mount, with 3 × 8 write threads on a
2-core CPU. This is the bottleneck described below: locally the write limits the drain, not RabbitMQ.

### What limits it and how to scale

- **One consumer is enough for the pilot.** Live traffic is about 86 messages (5,500 readings) every 30 minutes; a
  CA-08 resend is 768 messages. Even at the slowest rate above, both are stored in seconds, far inside the 30
  minutes before the next interval.
- **The bottleneck is the write, not RabbitMQ.** Each message is one object; the consumer writes a batch in 8
  threads. Locally it is the disk (Docker Desktop bind mounts on Windows are the slow case); in AWS each S3 PUT
  takes about 20-50 ms, so the parallel writes matter more than the number of consumers.
- **More consumers share the queue automatically.** Each one holds at most `CONSUMER_PREFETCH` unacknowledged
  messages, so RabbitMQ deals the backlog between them. Locally: `docker compose up -d --scale f3-consumer=3`.
  In AWS: the `desired_count` of the consumer ECS service.
- **When to scale:** if `readings.resend` is still above 0 when the next live interval arrives (30 minutes), or the
  live queue keeps growing. Rule of thumb: consumers = backlog ÷ (messages/s of one consumer × seconds allowed).
- **At 200,000 meters (US-58)** a live interval is about 3,125 messages (200,000 readings) and a full 24-hour resend
  of every meter would be 150,000 messages (9.6 million readings): about 13 minutes for one consumer at 190
  messages/s, about 5 minutes with three. That is when autoscaling on queue depth and a dedicated RabbitMQ cluster
  (ADR-014) are needed.
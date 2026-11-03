"""Measure how long the consumers take to drain a queue (US-31, T-31.2).

    python -m scripts.measure_drain                          # readings.resend, credentials from .env
    python -m scripts.measure_drain --queue readings.live --csv drain.csv

Start it after the resend is published and before starting the consumers. Four times per second it asks RabbitMQ
(over AMQP, the same RABBITMQ_URL as the simulator) how many messages are ready in the queue, and stops when none
are left:

    peak 784 messages, drained in 4.3 s, 182.3 messages/s, 11,141 readings/s (61.1 readings per message)

Why AMQP and not the web console API: the console refreshes its numbers every 5 seconds, too coarse for a resend
that drains in a few seconds. "Ready" does not count the last messages each consumer holds (at most its prefetch);
they are written within one batch time (RAW_BATCH_SECONDS) after the end reported here.
"""

import argparse
import csv
import os
import sys
import time
from dataclasses import dataclass

import pika
from dotenv import load_dotenv


@dataclass(frozen=True)
class Sample:
    elapsed: float   # seconds since the script started
    messages: int    # ready + unacknowledged


@dataclass(frozen=True)
class Drain:
    peak: int
    started_at: float
    finished_at: float

    @property
    def seconds(self) -> float:
        return self.finished_at - self.started_at

    @property
    def rate(self) -> float:
        return self.peak / self.seconds if self.seconds > 0 else float("inf")


def summarize(samples: list[Sample]) -> Drain | None:
    """Drain = from the last sample at the peak (consumers start taking messages) to the first empty sample after it."""
    if not samples:
        return None
    peak = max(s.messages for s in samples)
    if peak == 0:
        return None
    peak_index = max(i for i, s in enumerate(samples) if s.messages == peak)
    for s in samples[peak_index + 1:]:
        if s.messages == 0:
            return Drain(peak, samples[peak_index].elapsed, s.elapsed)
    return None


def queue_depth(channel, queue: str) -> int:
    """Messages ready in the queue (passive declare: it never creates or changes the queue)."""
    return channel.queue_declare(queue=queue, passive=True).method.message_count


def main() -> int:
    load_dotenv()
    p = argparse.ArgumentParser(description="Measure how long a RabbitMQ queue takes to drain")
    p.add_argument("--queue", default="readings.resend")
    p.add_argument("--rabbitmq-url", default=os.getenv("RABBITMQ_URL", "amqp://guest:guest@localhost:5672/%2F"))
    p.add_argument("--readings", type=int, default=None, help="readings in the resend, to report readings/s")
    p.add_argument("--timeout", type=float, default=1800, help="seconds")
    p.add_argument("--csv", default=None, help="also save every sample to this file")
    args = p.parse_args()

    connection = pika.BlockingConnection(pika.URLParameters(args.rabbitmq_url))
    channel = connection.channel()
    samples: list[Sample] = []
    start = time.monotonic()
    last_print = -1.0
    print(f"watching {args.queue} (Ctrl+C to stop)")
    try:
        while time.monotonic() - start < args.timeout:
            depth = queue_depth(channel, args.queue)
            samples.append(Sample(round(time.monotonic() - start, 2), depth))
            if samples[-1].elapsed - last_print >= 1:
                print(f"{samples[-1].elapsed:7.1f} s  {depth:>8,} messages", flush=True)
                last_print = samples[-1].elapsed
            if summarize(samples):
                break
            time.sleep(0.25)
    except KeyboardInterrupt:
        pass
    finally:
        connection.close()

    if args.csv:
        with open(args.csv, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["elapsed_s", "messages"])
            writer.writerows((s.elapsed, s.messages) for s in samples)

    drain = summarize(samples)
    if not drain:
        print("the queue did not fill and drain while watching", file=sys.stderr)
        return 1
    line = f"peak {drain.peak:,} messages, drained in {drain.seconds:.1f} s, {drain.rate:.1f} messages/s"
    if args.readings:
        per_message = args.readings / drain.peak
        line += f", {args.readings / drain.seconds:,.0f} readings/s ({per_message:.1f} readings per message)"
    print(line)
    return 0


if __name__ == "__main__":
    sys.exit(main())

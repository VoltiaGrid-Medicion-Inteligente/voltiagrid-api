"""Run the F3 consumer.

    python -m ingestion                         # until Ctrl+C
    python -m ingestion --exit-when-idle 30     # stop after 30 s without messages (drain a resend and finish)
"""

import argparse
import logging
import os
import signal

from dotenv import load_dotenv

from ingestion.consumer import (
    DEFAULT_BATCH_SECONDS,
    DEFAULT_BATCH_SIZE,
    DEFAULT_PREFETCH,
    ReadingConsumer,
    run,
)
from ingestion.raw_writer import LocalRawWriter, S3RawWriter


def build_parser() -> argparse.ArgumentParser:
    env = os.getenv
    p = argparse.ArgumentParser(description="F3 consumer: RabbitMQ -> raw layer")
    p.add_argument("--rabbitmq-url", default=env("RABBITMQ_URL", "amqp://guest:guest@localhost:5672/%2F"))
    p.add_argument("--raw-dir", default=env("RAW_DIR", "lake/raw"), help="local folder that plays the raw bucket")
    p.add_argument("--raw-bucket", default=env("RAW_BUCKET") or None,
                   help="S3 raw bucket; when set, --raw-dir is ignored")
    p.add_argument("--prefetch", type=int, default=int(env("CONSUMER_PREFETCH", str(DEFAULT_PREFETCH))))
    p.add_argument("--batch-size", type=int, default=int(env("RAW_BATCH_SIZE", str(DEFAULT_BATCH_SIZE))))
    p.add_argument("--batch-seconds", type=float, default=float(env("RAW_BATCH_SECONDS", str(DEFAULT_BATCH_SECONDS))))
    p.add_argument("--exit-when-idle", type=float, default=None, metavar="SECONDS")
    return p


def _stop_on_sigterm(signum, frame):
    raise KeyboardInterrupt


def main() -> None:
    load_dotenv()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    logging.getLogger("pika").setLevel(logging.WARNING)
    args = build_parser().parse_args()
    if args.prefetch < 1 or args.batch_size < 1:
        raise SystemExit("--prefetch and --batch-size must be 1 or more")
    signal.signal(signal.SIGTERM, _stop_on_sigterm)  # docker stop: write what is waiting and close cleanly
    writer = S3RawWriter(args.raw_bucket) if args.raw_bucket else LocalRawWriter(args.raw_dir)
    consumer = ReadingConsumer(writer, batch_size=args.batch_size, batch_seconds=args.batch_seconds)
    run(args.rabbitmq_url, consumer, prefetch=args.prefetch, exit_when_idle=args.exit_when_idle)


if __name__ == "__main__":
    main()

import argparse
import logging
import os
import time
from datetime import datetime, timezone

from dotenv import load_dotenv

from seed.defects import DefectCatalog
from simulators.common.consumption import HALF_HOUR
from simulators.common.inventory import Inventory, load_from_db, with_volume
from simulators.concentrator.contract import validate
from simulators.concentrator.generator import ConcentratorSimulator, outages_for_meters
from simulators.concentrator.publisher import MemoryPublisher, RabbitPublisher

log = logging.getLogger("simulators.concentrator")


def parse_utc(value: str) -> datetime:
    ts = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return ts if ts.tzinfo else ts.replace(tzinfo=timezone.utc)


def build_parser() -> argparse.ArgumentParser:
    env = os.getenv
    p = argparse.ArgumentParser(description="F3 concentrator simulator")
    p.add_argument("--seed", type=int, default=int(env("SIM_SEED", env("SEED", "42"))))
    p.add_argument("--meters", type=int, default=int(env("SIM_METERS", "0")),
                   help="volume to simulate (5,500 to 200,000); 0 = all meters in F4")
    p.add_argument("--no-db", action="store_true", help="use only synthetic meters (needs --meters)")
    p.add_argument("--start", type=parse_utc, default=parse_utc(env("SIM_START", "2013-01-01T00:00:00Z")))
    p.add_argument("--ticks", type=int, default=int(env("SIM_TICKS", "0")), help="0 = run forever")
    p.add_argument("--tick-seconds", type=float, default=float(env("SIM_TICK_SECONDS", "1800")))
    p.add_argument("--defect-rate", type=float, default=float(env("DEFECT_RATE", "0.02")))
    p.add_argument("--gap-rate", type=float, default=None, help="default = --defect-rate")
    p.add_argument("--outage-meters", type=int, default=int(env("SIM_OUTAGE_METERS", "0")))
    p.add_argument("--outage-start", type=parse_utc, default=None, help="default = --start")
    p.add_argument("--outage-hours", type=float, default=float(env("SIM_OUTAGE_HOURS", "24")))
    p.add_argument("--rabbitmq-url", default=env("RABBITMQ_URL", "amqp://guest:guest@localhost:5672/%2F"))
    p.add_argument("--database-url", default=env("DATABASE_URL"))
    p.add_argument("--dry-run", action="store_true", help="do not publish; log a summary per tick")
    p.add_argument("--no-validate", action="store_true", help="skip JSON Schema validation")
    return p


def load_inventory(args) -> Inventory:
    if args.no_db:
        if args.meters <= 0:
            raise SystemExit("--no-db needs --meters")
        return with_volume(Inventory({}), args.meters)
    if not args.database_url:
        raise SystemExit("DATABASE_URL is missing (or use --no-db --meters N)")
    base = load_from_db(args.database_url)
    if base.meter_count == 0:
        raise SystemExit("F4 has no meters: run the seed first (python -m seed)")
    return with_volume(base, args.meters) if args.meters else base


def main() -> None:
    load_dotenv()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    args = build_parser().parse_args()
    if not 0 <= args.defect_rate <= 1:
        raise SystemExit("--defect-rate must be between 0 and 1")

    inventory = load_inventory(args)
    outages = []
    if args.outage_meters:
        outages = outages_for_meters(inventory, args.outage_meters, args.outage_start or args.start,
                                     args.outage_hours)

    sim = ConcentratorSimulator(
        inventory=inventory,
        seed=args.seed,
        catalog=DefectCatalog(base_rate=args.defect_rate),
        gap_rate=args.defect_rate if args.gap_rate is None else args.gap_rate,
        outages=outages,
    )
    publisher = MemoryPublisher() if args.dry_run else RabbitPublisher(args.rabbitmq_url)
    log.info("meters=%s concentrators=%s outages=%s seed=%s",
             inventory.meter_count, len(sim.concentrators()), len(outages), args.seed)

    tick = 0
    try:
        while args.ticks == 0 or tick < args.ticks:
            interval_start = args.start + tick * HALF_HOUR
            envelopes = sim.tick(interval_start)
            for env in envelopes:
                if not args.no_validate:
                    validate(env.message)
                publisher.publish(env.routing_key, env.message)
            readings = sum(len(e.message["readings"]) for e in envelopes)
            resent = sum(1 for e in envelopes if e.message["is_resend"])
            log.info("interval %s: %s messages (%s resent), %s readings, %s held in outage",
                     interval_start.isoformat(), len(envelopes), resent, readings, sim.pending_resend())
            tick += 1
            if args.tick_seconds > 0 and (args.ticks == 0 or tick < args.ticks):
                time.sleep(args.tick_seconds)
    finally:
        publisher.close()
    log.info("done: %s", dict(sim.stats))


if __name__ == "__main__":
    main()
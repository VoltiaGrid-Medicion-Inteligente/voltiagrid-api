from collections import Counter
from datetime import datetime, timedelta, timezone

import pytest

from seed.defects import DefectCatalog
from simulators.common.consumption import HALF_HOUR, half_hour_kwh
from simulators.common.inventory import Inventory, with_volume
from simulators.concentrator.contract import validate, validation_errors
from simulators.concentrator.generator import (
    LIVE_ROUTING_KEY,
    RESEND_ROUTING_KEY,
    ConcentratorSimulator,
    Outage,
    outages_for_meters,
)
from simulators.concentrator.publisher import RabbitPublisher, message_properties

START = datetime(2013, 1, 1, tzinfo=timezone.utc)
TOLERANCE = 0.01


def small_inventory() -> Inventory:
    return Inventory({
        "TR-00001": [f"MAC{i:06d}" for i in range(1, 61)],
        "TR-00002": [f"MAC{i:06d}" for i in range(61, 131)],
    })


def clean_sim(inventory=None, **kw) -> ConcentratorSimulator:
    return ConcentratorSimulator(
        inventory=inventory or small_inventory(),
        catalog=DefectCatalog(base_rate=0.0),
        gap_rate=0.0,
        **kw,
    )


def run(sim, ticks):
    out = []
    for i in range(ticks):
        out.extend(sim.tick(START + i * HALF_HOUR))
    return out

def test_every_generated_message_follows_the_contract():
    sim = ConcentratorSimulator(inventory=small_inventory(), catalog=DefectCatalog(base_rate=0.2), gap_rate=0.2)
    for env in run(sim, 6):
        validate(env.message)


def test_contract_rejects_bad_messages():
    good = run(clean_sim(), 1)[0].message
    missing = {k: v for k, v in good.items() if k != "concentrator_id"}
    bad_energy = {**good, "readings": [{**good["readings"][0], "energy_kwh": "abc"}]}
    empty = {**good, "readings": []}
    assert validation_errors(good) == []
    assert validation_errors(missing)
    assert validation_errors(bad_energy)
    assert validation_errors(empty)

def test_one_message_per_concentrator_with_all_its_meters():
    envelopes = run(clean_sim(), 1)
    assert [e.message["concentrator_id"] for e in envelopes] == ["DC-TR-00001", "DC-TR-00002"]
    assert [len(e.message["readings"]) for e in envelopes] == [60, 70]
    assert all(e.routing_key == LIVE_ROUTING_KEY for e in envelopes)


def test_sequence_increases_per_concentrator_and_message_id_is_stable():
    envelopes = run(clean_sim(), 3)
    seqs = [e.message["sequence"] for e in envelopes if e.message["concentrator_id"] == "DC-TR-00001"]
    assert seqs == [1, 2, 3]
    assert envelopes[0].message["message_id"] == "DC-TR-00001-00000001"

def test_clean_values_come_from_the_shared_consumption_model():
    reading = run(clean_sim(), 1)[0].message["readings"][0]
    assert reading["energy_kwh"] == half_hour_kwh(reading["meter_id"], START, 42)
    assert reading["interval_start"] == "2013-01-01T00:00:00Z"

def test_same_seed_gives_the_same_messages():
    a = run(ConcentratorSimulator(inventory=small_inventory(), seed=7), 4)
    b = run(ConcentratorSimulator(inventory=small_inventory(), seed=7), 4)
    assert [e.message for e in a] == [e.message for e in b]

@pytest.mark.parametrize("rate", [0.02, 0.10])
def test_gaps_duplicates_and_skewed_clocks_at_the_configured_rate(rate):
    inventory = with_volume(Inventory({}), 2000)
    catalog = DefectCatalog(base_rate=rate)
    catalog.missing_day_rate = 0.0
    sim = ConcentratorSimulator(inventory=inventory, catalog=catalog, gap_rate=rate)
    envelopes = run(sim, 12)

    expected = sim.stats["expected"]
    assert expected == 2000 * 12
    assert abs(sim.stats["gap"] / expected - rate) <= TOLERANCE

    readings = [r for e in envelopes for r in e.message["readings"]]
    pairs = Counter((r["meter_id"], r["reading_seq"]) for r in readings)
    assert all(c == 1 for c in pairs.values())

    sent = expected - sim.stats["gap"]
    assert abs(sim.stats["duplicate"] / sent - rate) <= TOLERANCE
    skewed = sum(1 for r in readings if r["interval_start"][14:16] not in ("00", "30"))
    assert abs(skewed / len(readings) - rate) <= TOLERANCE * 2


def test_duplicate_keeps_meter_and_interval_with_higher_reading_seq():
    catalog = DefectCatalog(base_rate=0.0)
    catalog.duplicate_rate = 1.0
    sim = ConcentratorSimulator(inventory=small_inventory(), catalog=catalog, gap_rate=0.0)
    readings = run(sim, 1)[0].message["readings"]
    first, dup = readings[0], readings[1]
    assert (first["meter_id"], first["interval_start"]) == (dup["meter_id"], dup["interval_start"])
    assert dup["reading_seq"] > first["reading_seq"]


def test_rate_zero_sends_every_reading_clean():
    sim = clean_sim()
    readings = [r for e in run(sim, 4) for r in e.message["readings"]]
    assert len(readings) == 130 * 4
    assert all(isinstance(r["energy_kwh"], float) and 0 < r["energy_kwh"] < 25 for r in readings)

def test_outage_holds_messages_then_resends_them_in_bulk():
    outage = Outage("DC-TR-00001", START, START + timedelta(hours=24))
    sim = clean_sim(outages=[outage])

    during = run(sim, 48)
    assert all(e.message["concentrator_id"] != "DC-TR-00001" for e in during)
    assert sim.pending_resend() == 48

    after = sim.tick(START + timedelta(hours=24))
    resent = [e for e in after if e.routing_key == RESEND_ROUTING_KEY]
    assert len(resent) == 48
    assert all(e.message["is_resend"] for e in resent)
    assert [e.message["sequence"] for e in resent] == list(range(1, 49))
    assert sum(len(e.message["readings"]) for e in resent) == 60 * 48
    live = [e for e in after if e.routing_key == LIVE_ROUTING_KEY]
    assert {e.message["concentrator_id"] for e in live} == {"DC-TR-00001", "DC-TR-00002"}
    assert sim.pending_resend() == 0

def test_outage_for_1000_meters_over_24_hours_resends_48000_readings():
    inventory = with_volume(Inventory({}), 5500)
    outages = outages_for_meters(inventory, 1000, START, 24)
    sim = clean_sim(inventory=inventory, outages=outages)
    run(sim, 48)
    resent = [e for e in sim.tick(START + timedelta(hours=24)) if e.message["is_resend"]]
    affected = sum(len(inventory.meters_of(o.concentrator_id[3:])) for o in outages)
    assert affected >= 1000
    assert sum(len(e.message["readings"]) for e in resent) == affected * 48

@pytest.mark.parametrize("meters", [5500, 200000])
def test_volume_between_5500_and_200000(meters):
    sim = clean_sim(inventory=with_volume(Inventory({}), meters))
    envelopes = sim.tick(START)
    assert sum(len(e.message["readings"]) for e in envelopes) == meters

def test_volume_keeps_real_meters_first():
    base = small_inventory()
    inv = with_volume(base, 200)
    assert inv.meter_count == 200
    assert inv.meters_of("TR-00001") == base.meters_of("TR-00001")

def test_messages_are_persistent_and_carry_their_id():
    message = run(clean_sim(), 1)[0].message
    props = message_properties(message)
    assert props.delivery_mode == 2
    assert props.message_id == message["message_id"]
    assert props.content_type == "application/json"

def test_publish_is_mandatory_on_the_readings_exchange():
    class FakeChannel:
        def __init__(self):
            self.calls = []

        def basic_publish(self, **kwargs):
            self.calls.append(kwargs)

    pub = RabbitPublisher.__new__(RabbitPublisher)
    pub._channel = FakeChannel()
    message = run(clean_sim(), 1)[0].message
    pub.publish(LIVE_ROUTING_KEY, message)
    call = pub._channel.calls[0]
    assert call["exchange"] == "readings"
    assert call["routing_key"] == "readings.live"
    assert call["mandatory"] is True

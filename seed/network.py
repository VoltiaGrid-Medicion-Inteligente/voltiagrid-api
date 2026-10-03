"""Network topology seeding: circuits, transformers, meter→transformer assignment."""

import random
from dataclasses import dataclass
from decimal import Decimal
from typing import Dict, List

# Realistic capacity ranges (kVA)
TX_CAPACITY_KVA_MIN = Decimal("100.00")
TX_CAPACITY_KVA_MAX = Decimal("500.00")
CT_CAPACITY_KVA_MIN = Decimal("1000.00")
CT_CAPACITY_KVA_MAX = Decimal("5000.00")

# Topology constraints
METERS_PER_TX_MIN = 50
METERS_PER_TX_MAX = 80
TX_PER_CT_MIN = 5
TX_PER_CT_MAX = 10


@dataclass(frozen=True)
class NetworkPlan:
    circuits: List[Dict]
    transformers: List[Dict]
    meter_to_transformer: Dict[str, str]  # {lclid: transformer_code}


def _random_decimal(rng: random.Random, min_val: Decimal, max_val: Decimal) -> Decimal:
    """Generate random Decimal in [min_val, max_val)."""
    return min_val + (max_val - min_val) * Decimal(str(rng.random()))


def build_circuit(rng: random.Random, index: int) -> Dict:
    """Build a circuit dict with deterministic code and random capacity."""
    return {
        "code": f"CT-{index:03d}",
        "capacity_kva": _random_decimal(rng, CT_CAPACITY_KVA_MIN, CT_CAPACITY_KVA_MAX),
    }


def build_transformer(rng: random.Random, circuit_code: str, global_tx_index: int) -> Dict:
    """Build a transformer dict with deterministic code and random capacity."""
    return {
        "code": f"TR-{global_tx_index:05d}",
        "circuit_code": circuit_code,
        "capacity_kva": _random_decimal(rng, TX_CAPACITY_KVA_MIN, TX_CAPACITY_KVA_MAX),
    }


def plan_network(rng: random.Random, sorted_lclids: List[str]) -> NetworkPlan:
    """
    Create deterministic network topology:
    - Sort LCLids (already sorted by caller)
    - Assign 50-80 meters per transformer
    - Group 5-10 transformers per circuit
    - All randomness from provided RNG instance
    """
    # 1. Assign meters to transformers (contiguous blocks of 50-80)
    meter_to_tx: Dict[str, str] = {}
    tx_codes: List[str] = []
    
    i = 0
    tx_idx = 0
    while i < len(sorted_lclids):
        count = rng.randint(METERS_PER_TX_MIN, METERS_PER_TX_MAX)
        count = min(count, len(sorted_lclids) - i)
        
        tx_code = f"TR-{tx_idx:05d}"
        tx_codes.append(tx_code)
        
        for _ in range(count):
            meter_to_tx[sorted_lclids[i]] = tx_code
            i += 1
        tx_idx += 1

    # 2. Group transformers into circuits (5-10 per circuit)
    circuits: List[Dict] = []
    transformers: List[Dict] = []
    
    ct_idx = 0
    tx_pos = 0
    while tx_pos < len(tx_codes):
        circuit = build_circuit(rng, ct_idx)
        circuits.append(circuit)
        
        tx_in_ct = rng.randint(TX_PER_CT_MIN, TX_PER_CT_MAX)
        tx_in_ct = min(tx_in_ct, len(tx_codes) - tx_pos)
        
        for j in range(tx_in_ct):
            tx_code = tx_codes[tx_pos]
            tx = build_transformer(rng, circuit["code"], tx_pos)
            tx["code"] = tx_code
            transformers.append(tx)
            tx_pos += 1
        
        ct_idx += 1

    return NetworkPlan(
        circuits=circuits,
        transformers=transformers,
        meter_to_transformer=meter_to_tx,
    )
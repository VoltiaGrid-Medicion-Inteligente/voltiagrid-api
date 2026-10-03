import csv
from datetime import date
from pathlib import Path

DEFAULT_HOUSEHOLDS_CSV = Path("data/raw/informations_households.csv")
TARIFF_BY_CODE =  {"Std":"standard", "ToU": "dynamic"}
VALID_GROUPED = {"Affluent", "Comfortable", "Adversity"}
REGISTER = {"code": "CU-MAC000002", "acorn_group": "ACORN-A"}
CONTRACT_START_DATE = date(2011, 11, 1)


def read_households(path=DEFAULT_HOUSEHOLDS_CSV):
    with open(path, newline="", encoding="utf-8-sig") as file:
        return list(csv.DictReader(file))
    
    
def map_tariff(code):
    if code not in TARIFF_BY_CODE:
        raise ValueError(f"Tarifa desconocida: '{code}'")
    return TARIFF_BY_CODE[code]


def select_households(rows, count):
    ordered = sorted(rows, key=lambda row: row["LCLid"])
    return ordered[:count]


def normalize_acorn(value):
    if value == "ACORN-":
        return "UNKNOWN"
    return value


def normalize_grouped(value):
    if value in VALID_GROUPED:
        return value
    return "Unknown"


def build_customer(row):
    return {
        "code": f"CU-{row['LCLid']}",
        "acorn_group": normalize_acorn(row["Acorn"]),
        "acorn_grouped": normalize_grouped(row["Acorn_grouped"]),
    }


def build_contract(row):
    return {
        "code": f"CT-{row['LCLid']}-1",
        "customer_code": f"CU-{row['LCLid']}",
        "tariff_type": map_tariff(row["stdorToU"]),
        "start_date": CONTRACT_START_DATE,
        "end_date": None,
    }


def build_meter(row, transformer_code: str | None = None):
    meter = {
        "lclid": row["LCLid"],
        "customer_code": f"CU-{row['LCLid']}",
    }
    if transformer_code:
        meter["transformer_code"] = transformer_code
    return meter


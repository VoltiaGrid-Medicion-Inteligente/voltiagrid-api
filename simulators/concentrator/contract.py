import json
from functools import lru_cache
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker

SCHEMA_PATH = Path(__file__).parent / "schema" / "reading_batch.v1.json"
SCHEMA_VERSION = "1.0"


@lru_cache(maxsize=1)
def load_schema() -> dict:
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def _validator() -> Draft202012Validator:
    schema = load_schema()
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema, format_checker=FormatChecker())


def validation_errors(message: dict) -> list[str]:
    """Every problem in the message, as readable text. Empty list = valid."""
    return [
        f"{'/'.join(str(p) for p in error.absolute_path) or '<root>'}: {error.message}"
        for error in _validator().iter_errors(message)
    ]


def validate(message: dict) -> None:
    """Raise ValueError if the message does not follow the contract."""
    errors = validation_errors(message)
    if errors:
        raise ValueError("Invalid reading batch: " + "; ".join(errors))
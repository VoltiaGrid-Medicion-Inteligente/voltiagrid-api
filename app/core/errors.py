"""Domain errors shared by the APIs (US-18).

Services raise these; they never build HTTP responses. T-18.3 turns them into
the single JSON error format of the APIs.
"""


class NotFoundError(Exception):
    """A resource identified by its natural key does not exist."""

    def __init__(self, resource: str, key: str):
        self.resource, self.key = resource, key
        super().__init__(f"{resource} '{key}' not found")


class ConflictError(Exception):
    """The natural key of a new resource already exists."""

    def __init__(self, resource: str, key: str):
        self.resource, self.key = resource, key
        super().__init__(f"{resource} '{key}' already exists")

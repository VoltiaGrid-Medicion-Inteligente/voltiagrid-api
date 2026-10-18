"""US-13 (T-13.3): the isolation rule lives in the service layer, not only in the router."""

import pytest

from app.api.common import Principal
from app.api.customer_consumption.repository import InMemoryConsumptionRepository
from app.api.customer_consumption.service import (
    AccessDenied,
    ConsumptionService,
    CustomerNotFound,
    can_read_consumption,
)
from app.core.tariffs import TariffCalendar

ALICE = Principal(role="customer", customer_code="CU-MAC000002")
INTERNAL = Principal(role="internal")


@pytest.fixture
def service():
    repo = InMemoryConsumptionRepository({"CU-MAC000002": ["MAC000002"], "CU-MAC000003": ["MAC000003"]})
    return ConsumptionService(repo, TariffCalendar.from_csv("data/reference/tariffs.csv"), seed=42, defect_rate=0)


def test_rule_customer_reads_only_own_data():
    assert can_read_consumption(ALICE, "CU-MAC000002") is True
    assert can_read_consumption(ALICE, "CU-MAC000003") is False


def test_rule_internal_reads_any_customer():
    assert can_read_consumption(INTERNAL, "CU-MAC000003") is True


def test_service_refuses_another_customers_data(service):
    with pytest.raises(AccessDenied):
        service.daily(ALICE, "CU-MAC000003", "2013-02")


def test_service_answers_403_before_404_to_customers(service):
    # A customer must not learn whether another code exists.
    with pytest.raises(AccessDenied):
        service.daily(ALICE, "CU-DOES-NOT-EXIST", "2013-02")


def test_service_gives_internal_users_any_customer(service):
    assert service.daily(INTERNAL, "CU-MAC000003", "2013-02")["customer_code"] == "CU-MAC000003"


def test_service_unknown_customer_for_internal_user(service):
    with pytest.raises(CustomerNotFound):
        service.daily(INTERNAL, "CU-DOES-NOT-EXIST", "2013-02")

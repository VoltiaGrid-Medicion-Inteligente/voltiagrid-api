"""Load test of the customer consumption API (US-47, T-47.1, RNF-04: p95 <= 500 ms).

Every simulated user is one customer: it logs in once and then asks for its daily consumption of one month, the call
behind the customer's main screen. Customers are taken from the inventory API (an internal token), so the test uses
the customers of whatever seed the database has.

    docker compose up -d                      # the stack (or make up); the API on 8001, the inventory on 8003
    locust -f loadtest/locustfile.py --headless -u 20 -r 5 -t 2m --host http://localhost:8001 `
           --csv loadtest/results/before --only-summary
    python -m loadtest.report loadtest/results/before_stats.csv

Environment: DEMO_CUSTOMER_PASSWORD and DEMO_INTERNAL_PASSWORD (from .env), LOADTEST_MONTH (default 2013-01),
INVENTORY_URL (default http://localhost:8003), LOADTEST_CUSTOMERS (how many customers to use, default 50).
"""

import os
import random

import requests
from dotenv import load_dotenv
from locust import HttpUser, between, events, task

load_dotenv()

MONTH = os.getenv("LOADTEST_MONTH", "2013-01")
INVENTORY_URL = os.getenv("INVENTORY_URL", "http://localhost:8003")
CUSTOMERS: list[str] = []


@events.test_start.add_listener
def load_customers(environment, **_kwargs):
    """Customer codes from the inventory API, once for the whole test."""
    token = requests.post(f"{environment.host}/auth/token", timeout=10,
                          json={"username": "internal", "password": os.environ["DEMO_INTERNAL_PASSWORD"]})
    token.raise_for_status()
    headers = {"Authorization": f"Bearer {token.json()['access_token']}"}
    size = int(os.getenv("LOADTEST_CUSTOMERS", "50"))
    page = requests.get(f"{INVENTORY_URL}/customers", params={"size": size}, headers=headers, timeout=10)
    page.raise_for_status()
    CUSTOMERS[:] = [c["code"] for c in page.json()["items"]]
    if not CUSTOMERS:
        raise RuntimeError("the inventory has no customers: run the seed first")
    print(f"load test: {len(CUSTOMERS)} customers, month {MONTH}")


class Customer(HttpUser):
    wait_time = between(0.5, 1.5)

    def on_start(self):
        self.code = random.choice(CUSTOMERS)
        login = self.client.post("/auth/token", name="/auth/token",
                                 json={"username": self.code, "password": os.environ["DEMO_CUSTOMER_PASSWORD"]})
        self.headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    @task
    def daily_consumption(self):
        self.client.get(f"/me/consumption/daily?month={MONTH}", name="/me/consumption/daily", headers=self.headers)

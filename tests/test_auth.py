"""US-13 (T-13.1): JWT with roles and expiry; a request without a valid token gets 401."""

import jwt
import pytest
from fastapi.testclient import TestClient

from app.core.security import InvalidToken, decode_token, issue_token

MONTH = {"month": "2013-02"}


@pytest.fixture
def client(consumption_app):
    return TestClient(consumption_app)


def _bearer(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def test_customer_token_carries_role_and_customer_code():
    claims = decode_token(issue_token("customer", customer_code="CU-MAC000002"))
    assert claims["role"] == "customer"
    assert claims["sub"] == "CU-MAC000002"
    assert claims["exp"] > claims["iat"]


def test_customer_token_needs_a_customer_code():
    with pytest.raises(ValueError):
        issue_token("customer")


def test_expired_token_is_rejected(client):
    expired = issue_token("internal", expires_minutes=-1)
    with pytest.raises(InvalidToken, match="expired"):
        decode_token(expired)
    assert client.get("/me/consumption/daily", params=MONTH, headers=_bearer(expired)).status_code == 401


def test_token_signed_with_another_key_is_rejected(client):
    forged = jwt.encode({"sub": "internal", "role": "internal", "iss": "voltiagrid", "iat": 0, "exp": 9999999999},
                        "another-key-that-is-long-enough-for-hs256", algorithm="HS256")
    assert client.get("/me/consumption/daily", params=MONTH, headers=_bearer(forged)).status_code == 401


def test_unknown_role_is_rejected():
    from app.core.config import get_settings
    bad = jwt.encode({"sub": "x", "role": "admin", "iss": "voltiagrid", "iat": 0, "exp": 9999999999},
                     get_settings().jwt_secret, algorithm="HS256")
    with pytest.raises(InvalidToken):
        decode_token(bad)


def test_no_token_is_401(client):
    r = client.get("/me/consumption/daily", params=MONTH)
    assert r.status_code == 401
    assert r.json()["detail"] == "Missing bearer token"


def test_login_customer_and_use_the_token(client):
    r = client.post("/auth/token", json={"username": "CU-MAC000002", "password": "test-customer-password"})
    assert r.status_code == 200
    token = r.json()["access_token"]
    assert decode_token(token)["sub"] == "CU-MAC000002"
    assert client.get("/me/consumption/daily", params=MONTH, headers=_bearer(token)).status_code == 200


def test_login_internal(client):
    r = client.post("/auth/token", json={"username": "internal", "password": "test-internal-password"})
    assert r.status_code == 200
    assert decode_token(r.json()["access_token"])["role"] == "internal"


@pytest.mark.parametrize("username,password", [
    ("CU-MAC000002", "wrong"),
    ("internal", "test-customer-password"),
    ("MAC000002", "test-customer-password"),
])
def test_wrong_credentials_are_401(client, username, password):
    r = client.post("/auth/token", json={"username": username, "password": password})
    assert r.status_code == 401

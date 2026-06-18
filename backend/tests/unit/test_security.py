"""Unit tests for security utilities."""
from __future__ import annotations

import pytest
from app.core.security import (
    TokenData,
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from app.core.exceptions import InvalidToken, TokenExpired


class TestPasswordHashing:
    def test_hash_and_verify(self):
        pwd = "S3cur3P@ssword!"
        hashed = hash_password(pwd)
        assert hashed != pwd
        assert verify_password(pwd, hashed) is True

    def test_wrong_password_fails(self):
        hashed = hash_password("correct-horse")
        assert verify_password("battery-staple", hashed) is False

    def test_hash_is_different_each_time(self):
        h1 = hash_password("same-password")
        h2 = hash_password("same-password")
        assert h1 != h2  # bcrypt salts are unique


class TestJWT:
    def test_access_token_round_trip(self):
        token = create_access_token(
            subject="test@epims.local",
            user_id="00000000-0000-0000-0000-000000000001",
            roles=["approver"],
            permissions=["purchase_orders:read"],
        )
        payload = decode_token(token, expected_type="access")
        assert payload["sub"] == "test@epims.local"
        assert "approver" in payload["rls"]
        assert "purchase_orders:read" in payload["pms"]

    def test_refresh_token_round_trip(self):
        token = create_refresh_token(
            subject="test@epims.local",
            user_id="00000000-0000-0000-0000-000000000001",
        )
        payload = decode_token(token, expected_type="refresh")
        assert payload["type"] == "refresh"

    def test_wrong_token_type_raises(self):
        access = create_access_token(
            subject="x", user_id="00000000-0000-0000-0000-000000000001",
            roles=[], permissions=[]
        )
        with pytest.raises(InvalidToken):
            decode_token(access, expected_type="refresh")

    def test_token_data_has_permission(self):
        token = create_access_token(
            subject="test@epims.local",
            user_id="00000000-0000-0000-0000-000000000001",
            roles=["buyer"],
            permissions=["purchase_orders:create", "purchase_orders:read"],
        )
        payload = decode_token(token)
        td = TokenData(payload)
        assert td.has_permission("purchase_orders", "create") is True
        assert td.has_permission("invoices", "approve") is False

    def test_token_data_has_role(self):
        token = create_access_token(
            subject="test@epims.local",
            user_id="00000000-0000-0000-0000-000000000001",
            roles=["buyer", "approver"],
            permissions=[],
        )
        payload = decode_token(token)
        td = TokenData(payload)
        assert td.has_role("approver") is True
        assert td.has_role("superuser") is False
        assert td.has_role("buyer", "superuser") is True  # OR semantics

"""Unit tests for authentication."""

import pytest
from app.core.security import (
    get_password_hash,
    verify_password,
    create_access_token,
    create_refresh_token,
    verify_token,
    decode_token,
)


class TestPasswordHashing:
    """Tests for password hashing."""

    def test_hash_password(self):
        """Test password hashing."""
        password = "TestPassword123!"
        hashed = get_password_hash(password)

        assert hashed != password
        assert len(hashed) > 0

    def test_verify_password_correct(self):
        """Test verifying correct password."""
        password = "TestPassword123!"
        hashed = get_password_hash(password)

        assert verify_password(password, hashed) is True

    def test_verify_password_incorrect(self):
        """Test verifying incorrect password."""
        password = "TestPassword123!"
        hashed = get_password_hash(password)

        assert verify_password("WrongPassword", hashed) is False

    def test_different_passwords_different_hashes(self):
        """Test that different passwords produce different hashes."""
        password1 = "Password1!"
        password2 = "Password2!"

        hash1 = get_password_hash(password1)
        hash2 = get_password_hash(password2)

        assert hash1 != hash2


class TestJWTTokens:
    """Tests for JWT token handling."""

    def test_create_access_token(self):
        """Test access token creation."""
        user_id = "test-user-id"
        token = create_access_token(user_id)

        assert token is not None
        assert isinstance(token, str)
        assert len(token) > 0

    def test_create_refresh_token(self):
        """Test refresh token creation."""
        user_id = "test-user-id"
        token = create_refresh_token(user_id)

        assert token is not None
        assert isinstance(token, str)
        assert len(token) > 0

    def test_verify_access_token(self):
        """Test access token verification."""
        user_id = "test-user-id"
        token = create_access_token(user_id)

        result = verify_token(token, "access")
        assert result == user_id

    def test_verify_refresh_token(self):
        """Test refresh token verification."""
        user_id = "test-user-id"
        token = create_refresh_token(user_id)

        result = verify_token(token, "refresh")
        assert result == user_id

    def test_verify_token_wrong_type(self):
        """Test verifying token with wrong type."""
        user_id = "test-user-id"
        access_token = create_access_token(user_id)

        result = verify_token(access_token, "refresh")
        assert result is None

    def test_decode_token(self):
        """Test decoding token."""
        user_id = "test-user-id"
        token = create_access_token(user_id)

        payload = decode_token(token)
        assert payload is not None
        assert payload["sub"] == user_id
        assert payload["type"] == "access"

    def test_decode_invalid_token(self):
        """Test decoding invalid token."""
        result = decode_token("invalid-token")
        assert result is None

    def test_access_and_refresh_tokens_different(self):
        """Test that access and refresh tokens are different."""
        user_id = "test-user-id"
        access_token = create_access_token(user_id)
        refresh_token = create_refresh_token(user_id)

        assert access_token != refresh_token

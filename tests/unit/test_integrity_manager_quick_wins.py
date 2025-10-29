"""
Unit tests for IntegrityManager quick wins (improve coverage 21% → ~35%).

Tests cover:
- read_salt() / write_salt() I/O
- derive_key() crypto operations
- compute_sha256() hashing
- create_portfolio_block() / decrypt_portfolio_block() encryption
"""

from __future__ import annotations

import contextlib
import json
import secrets
import tempfile
from pathlib import Path

import pytest
from src.core.integrity_manager import IntegrityManager


class TestIntegrityManagerSaltIO:
    """Test salt read/write operations."""

    def setup_method(self) -> None:
        """Setup temp directory."""
        self.temp_dir = tempfile.mkdtemp()
        self.temp_path = Path(self.temp_dir)
        self.regexlab_dir = self.temp_path / ".regexlab"
        self.manager = IntegrityManager(self.regexlab_dir)

    def teardown_method(self) -> None:
        """Clean up temp directory."""
        with contextlib.suppress(Exception):
            import shutil

            shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_read_salt_file_not_exists(self):
        """Test read_salt returns None when file doesn't exist."""
        result = self.manager.read_salt()

        assert result is None

    def test_write_salt_creates_directory(self):
        """Test write_salt creates .regexlab directory if missing."""
        salt = secrets.token_bytes(32)

        self.manager.write_salt(salt)

        assert self.regexlab_dir.exists()
        assert self.manager.salt_file.exists()
        assert self.manager.salt_file.read_bytes() == salt

    def test_read_salt_returns_written_salt(self):
        """Test read_salt returns salt written by write_salt."""
        salt = secrets.token_bytes(32)
        self.manager.write_salt(salt)

        result = self.manager.read_salt()

        assert result == salt

    def test_write_salt_overwrites_existing(self):
        """Test write_salt overwrites existing salt file."""
        old_salt = secrets.token_bytes(32)
        new_salt = secrets.token_bytes(32)

        self.manager.write_salt(old_salt)
        self.manager.write_salt(new_salt)

        result = self.manager.read_salt()
        assert result == new_salt
        assert result != old_salt


class TestIntegrityManagerKeyDerivation:
    """Test derive_key() crypto operations."""

    def setup_method(self) -> None:
        """Setup temp directory."""
        self.temp_dir = tempfile.mkdtemp()
        self.temp_path = Path(self.temp_dir)
        self.regexlab_dir = self.temp_path / ".regexlab"
        self.manager = IntegrityManager(self.regexlab_dir)

    def teardown_method(self) -> None:
        """Clean up temp directory."""
        with contextlib.suppress(Exception):
            import shutil

            shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_derive_key_returns_32_bytes(self):
        """Test derive_key returns 32-byte key."""
        salt = secrets.token_bytes(32)
        context = "abc123def456"

        key = self.manager.derive_key(salt, context)

        assert len(key) == 32
        assert isinstance(key, bytes)

    def test_derive_key_deterministic(self):
        """Test derive_key produces same key for same inputs."""
        salt = secrets.token_bytes(32)
        context = "test_context_123"

        key1 = self.manager.derive_key(salt, context)
        key2 = self.manager.derive_key(salt, context)

        assert key1 == key2

    def test_derive_key_different_salt_different_key(self):
        """Test different salt produces different key."""
        salt1 = secrets.token_bytes(32)
        salt2 = secrets.token_bytes(32)
        context = "same_context"

        key1 = self.manager.derive_key(salt1, context)
        key2 = self.manager.derive_key(salt2, context)

        assert key1 != key2

    def test_derive_key_different_context_different_key(self):
        """Test different context produces different key."""
        salt = secrets.token_bytes(32)
        context1 = "context_A"
        context2 = "context_B"

        key1 = self.manager.derive_key(salt, context1)
        key2 = self.manager.derive_key(salt, context2)

        assert key1 != key2


class TestIntegrityManagerSHA256:
    """Test compute_sha256() hashing."""

    def setup_method(self) -> None:
        """Setup temp directory."""
        self.temp_dir = tempfile.mkdtemp()
        self.temp_path = Path(self.temp_dir)
        self.regexlab_dir = self.temp_path / ".regexlab"
        self.manager = IntegrityManager(self.regexlab_dir)

    def teardown_method(self) -> None:
        """Clean up temp directory."""
        with contextlib.suppress(Exception):
            import shutil

            shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_compute_sha256_known_value(self):
        """Test compute_sha256 with known test vector."""
        data = b"hello world"

        result = self.manager.compute_sha256(data)

        # Known SHA256 of "hello world"
        expected = "b94d27b9934d3e08a52e52d7da7dabfac484efe37a5380ee9088f7ace2efcde9"
        assert result == expected

    def test_compute_sha256_deterministic(self):
        """Test compute_sha256 produces same hash for same data."""
        data = b"test data 123"

        hash1 = self.manager.compute_sha256(data)
        hash2 = self.manager.compute_sha256(data)

        assert hash1 == hash2

    def test_compute_sha256_different_data_different_hash(self):
        """Test different data produces different hash."""
        data1 = b"data A"
        data2 = b"data B"

        hash1 = self.manager.compute_sha256(data1)
        hash2 = self.manager.compute_sha256(data2)

        assert hash1 != hash2

    def test_compute_sha256_returns_hex_string(self):
        """Test compute_sha256 returns lowercase hex string."""
        data = b"test"

        result = self.manager.compute_sha256(data)

        assert isinstance(result, str)
        assert len(result) == 64  # SHA256 is 256 bits = 32 bytes = 64 hex chars
        assert result == result.lower()
        assert all(c in "0123456789abcdef" for c in result)


class TestIntegrityManagerPortfolioBlocks:
    """Test create_portfolio_block() and decrypt_portfolio_block()."""

    def setup_method(self) -> None:
        """Setup temp directory."""
        self.temp_dir = tempfile.mkdtemp()
        self.temp_path = Path(self.temp_dir)
        self.regexlab_dir = self.temp_path / ".regexlab"
        self.manager = IntegrityManager(self.regexlab_dir)

    def teardown_method(self) -> None:
        """Clean up temp directory."""
        with contextlib.suppress(Exception):
            import shutil

            shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_create_portfolio_block_returns_sha256_and_encrypted(self):
        """Test create_portfolio_block returns SHA256 and encrypted data."""
        salt = secrets.token_bytes(32)
        portfolio_json = '{"name": "Test", "patterns": []}'

        sha256, encrypted = self.manager.create_portfolio_block(salt, portfolio_json)

        assert isinstance(sha256, str)
        assert len(sha256) == 64  # SHA256 hex
        assert isinstance(encrypted, bytes)
        assert len(encrypted) == len(portfolio_json.encode("utf-8"))

    def test_create_decrypt_roundtrip(self):
        """Test creating and decrypting portfolio block (roundtrip)."""
        salt = secrets.token_bytes(32)
        portfolio_json = '{"name": "Test Portfolio", "version": "1.0.0", "patterns": []}'

        sha256, encrypted = self.manager.create_portfolio_block(salt, portfolio_json)
        decrypted = self.manager.decrypt_portfolio_block(salt, sha256, encrypted)

        assert decrypted == portfolio_json

    def test_decrypt_portfolio_block_wrong_sha256_raises(self):
        """Test decrypt_portfolio_block raises on SHA256 mismatch."""
        salt = secrets.token_bytes(32)
        portfolio_json = '{"name": "Test", "patterns": []}'

        _sha256, encrypted = self.manager.create_portfolio_block(salt, portfolio_json)

        # Corrupt SHA256
        wrong_sha256 = "0" * 64

        with pytest.raises(ValueError, match="SHA256 mismatch"):
            self.manager.decrypt_portfolio_block(salt, wrong_sha256, encrypted)

    def test_decrypt_portfolio_block_wrong_salt_raises(self):
        """Test decrypt_portfolio_block raises on wrong salt."""
        salt = secrets.token_bytes(32)
        wrong_salt = secrets.token_bytes(32)
        portfolio_json = '{"name": "Test", "patterns": []}'

        sha256, encrypted = self.manager.create_portfolio_block(salt, portfolio_json)

        with pytest.raises(ValueError, match="SHA256 mismatch"):
            self.manager.decrypt_portfolio_block(wrong_salt, sha256, encrypted)

    def test_create_portfolio_block_deterministic(self):
        """Test create_portfolio_block produces same output for same inputs."""
        salt = secrets.token_bytes(32)
        portfolio_json = '{"name": "Test", "patterns": []}'

        sha256_1, encrypted_1 = self.manager.create_portfolio_block(salt, portfolio_json)
        sha256_2, encrypted_2 = self.manager.create_portfolio_block(salt, portfolio_json)

        assert sha256_1 == sha256_2
        assert encrypted_1 == encrypted_2

    def test_create_portfolio_block_different_json_different_output(self):
        """Test different JSON produces different encrypted output."""
        salt = secrets.token_bytes(32)
        json1 = '{"name": "Portfolio A", "patterns": []}'
        json2 = '{"name": "Portfolio B", "patterns": []}'

        sha256_1, encrypted_1 = self.manager.create_portfolio_block(salt, json1)
        sha256_2, encrypted_2 = self.manager.create_portfolio_block(salt, json2)

        assert sha256_1 != sha256_2
        assert encrypted_1 != encrypted_2

    def test_create_portfolio_block_complex_json(self):
        """Test create_portfolio_block with complex portfolio JSON."""
        salt = secrets.token_bytes(32)
        portfolio = {
            "name": "Complex Portfolio",
            "description": "With patterns",
            "version": "2.0.0",
            "patterns": [
                {"name": "Email", "regex": r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", "type": "static"},
                {"name": "URL", "regex": r"https?://[^\s]+", "type": "static"},
            ],
        }
        portfolio_json = json.dumps(portfolio, indent=2)

        block_sha256, encrypted = self.manager.create_portfolio_block(salt, portfolio_json)
        decrypted = self.manager.decrypt_portfolio_block(salt, block_sha256, encrypted)

        assert decrypted == portfolio_json
        decrypted_dict = json.loads(decrypted)
        assert decrypted_dict == portfolio

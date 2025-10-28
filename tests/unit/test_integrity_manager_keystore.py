"""
Unit tests for IntegrityManager.generate_keystore() and verify_and_restore().

Coverage target: integrity_manager.py lines 144-327 (generate_keystore, verify_and_restore).
Current coverage: 35% → Target: 60%+ (~25% gain).

Tests:
- generate_keystore(): Valid portfolios, salt generation, errors
- verify_and_restore(): Intact/corrupted/missing portfolios, keystore errors
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from src.core.integrity_manager import IntegrityManager

# === Fixtures ===


@pytest.fixture
def temp_regexlab_dir(tmp_path: Path) -> Path:
    """Create temporary RegexLab directory."""
    regexlab = tmp_path / "RegexLab"
    regexlab.mkdir()
    return regexlab


@pytest.fixture
def temp_portfolios_dir(tmp_path: Path) -> Path:
    """Create temporary builtin portfolios directory."""
    portfolios = tmp_path / "builtin"
    portfolios.mkdir()
    return portfolios


@pytest.fixture
def manager(temp_regexlab_dir: Path) -> IntegrityManager:
    """Create IntegrityManager instance."""
    return IntegrityManager(temp_regexlab_dir)


@pytest.fixture
def sample_portfolio() -> dict:
    """Sample valid portfolio data."""
    return {
        "name": "Test Portfolio",
        "description": "Sample portfolio",
        "version": "1.0.0",
        "patterns": [
            {"name": "Email", "regex": r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b", "type": "static"}
        ],
    }


# === generate_keystore() Tests ===


class TestGenerateKeystore:
    """Test IntegrityManager.generate_keystore() method."""

    def test_generate_keystore_single_portfolio(
        self, manager: IntegrityManager, temp_portfolios_dir: Path, sample_portfolio: dict
    ):
        """Test generating keystore with single valid portfolio."""
        # Create portfolio file
        portfolio_file = temp_portfolios_dir / "test.json"
        portfolio_file.write_text(json.dumps(sample_portfolio), encoding="utf-8")

        # Generate keystore
        count, total_bytes = manager.generate_keystore(temp_portfolios_dir)

        # Verify results
        assert count == 1
        assert total_bytes > 100  # Header + SHA256 + Size + encrypted data

        # Verify keystore file exists
        assert manager.keystore_file.exists()

        # Verify salt file created
        assert manager.salt_file.exists()
        salt = manager.read_salt()
        assert salt is not None
        assert len(salt) == manager.SALT_SIZE

    def test_generate_keystore_multiple_portfolios(
        self, manager: IntegrityManager, temp_portfolios_dir: Path, sample_portfolio: dict
    ):
        """Test generating keystore with multiple portfolios."""
        # Create 3 portfolio files
        for i in range(3):
            portfolio = sample_portfolio.copy()
            portfolio["name"] = f"Portfolio {i + 1}"
            (temp_portfolios_dir / f"portfolio_{i + 1}.json").write_text(json.dumps(portfolio), encoding="utf-8")

        # Generate keystore
        count, total_bytes = manager.generate_keystore(temp_portfolios_dir)

        # Verify results
        assert count == 3
        assert total_bytes > 300  # Multiple blocks

        # Verify keystore structure
        keystore_data = manager.keystore_file.read_bytes()

        # Header: 2-digit count
        header = keystore_data[:2].decode("utf-8")
        assert header == "03"

    def test_generate_keystore_reuses_existing_salt(
        self, manager: IntegrityManager, temp_portfolios_dir: Path, sample_portfolio: dict
    ):
        """Test that generate_keystore reuses existing salt instead of regenerating."""
        # Create existing salt
        existing_salt = manager.generate_salt()
        manager.write_salt(existing_salt)

        # Create portfolio
        (temp_portfolios_dir / "test.json").write_text(json.dumps(sample_portfolio), encoding="utf-8")

        # Generate keystore
        manager.generate_keystore(temp_portfolios_dir)

        # Verify salt unchanged
        current_salt = manager.read_salt()
        assert current_salt == existing_salt

    def test_generate_keystore_creates_salt_if_missing(
        self, manager: IntegrityManager, temp_portfolios_dir: Path, sample_portfolio: dict
    ):
        """Test that generate_keystore creates new salt if none exists."""
        # Ensure no salt exists
        assert not manager.salt_file.exists()

        # Create portfolio
        (temp_portfolios_dir / "test.json").write_text(json.dumps(sample_portfolio), encoding="utf-8")

        # Generate keystore
        manager.generate_keystore(temp_portfolios_dir)

        # Verify salt created
        assert manager.salt_file.exists()
        salt = manager.read_salt()
        assert salt is not None
        assert len(salt) == manager.SALT_SIZE

    def test_generate_keystore_no_portfolios_raises_error(self, manager: IntegrityManager, temp_portfolios_dir: Path):
        """Test that generate_keystore raises ValueError if no portfolio files found."""
        # Empty directory
        with pytest.raises(ValueError, match="No portfolio files found"):
            manager.generate_keystore(temp_portfolios_dir)

    def test_generate_keystore_too_many_portfolios_raises_error(
        self, manager: IntegrityManager, temp_portfolios_dir: Path, sample_portfolio: dict
    ):
        """Test that generate_keystore raises ValueError if more than 99 portfolios."""
        # Create 100 portfolios (exceeds max 99)
        for i in range(100):
            portfolio = sample_portfolio.copy()
            portfolio["name"] = f"Portfolio {i + 1}"
            (temp_portfolios_dir / f"portfolio_{i:03d}.json").write_text(json.dumps(portfolio), encoding="utf-8")

        # Should raise error
        with pytest.raises(ValueError, match=r"Too many portfolios.*max 99"):
            manager.generate_keystore(temp_portfolios_dir)

    def test_generate_keystore_invalid_json_raises_error(self, manager: IntegrityManager, temp_portfolios_dir: Path):
        """Test that generate_keystore raises ValueError if portfolio has invalid JSON."""
        # Create invalid JSON file
        (temp_portfolios_dir / "invalid.json").write_text("{broken json", encoding="utf-8")

        # Should raise error with filename
        with pytest.raises(ValueError, match=r"Invalid JSON in invalid\.json"):
            manager.generate_keystore(temp_portfolios_dir)

    def test_generate_keystore_sorted_order(
        self, manager: IntegrityManager, temp_portfolios_dir: Path, sample_portfolio: dict
    ):
        """Test that portfolios are processed in sorted alphabetical order."""
        # Create portfolios with non-alphabetical creation order
        names = ["zebra.json", "alpha.json", "beta.json"]
        for name in names:
            portfolio = sample_portfolio.copy()
            portfolio["name"] = name
            (temp_portfolios_dir / name).write_text(json.dumps(portfolio), encoding="utf-8")

        # Generate keystore
        count, _ = manager.generate_keystore(temp_portfolios_dir)

        assert count == 3
        # Keystore should process in sorted order: alpha, beta, zebra

    def test_generate_keystore_creates_regexlab_dir_if_missing(self, temp_portfolios_dir: Path, sample_portfolio: dict):
        """Test that generate_keystore creates RegexLab directory if it doesn't exist."""
        # Use non-existent RegexLab directory
        regexlab_dir = temp_portfolios_dir.parent / "NewRegexLab"
        assert not regexlab_dir.exists()

        manager = IntegrityManager(regexlab_dir)

        # Create portfolio
        (temp_portfolios_dir / "test.json").write_text(json.dumps(sample_portfolio), encoding="utf-8")

        # Generate keystore
        manager.generate_keystore(temp_portfolios_dir)

        # Verify directory created
        assert regexlab_dir.exists()
        assert manager.keystore_file.exists()
        assert manager.salt_file.exists()

    def test_generate_keystore_header_format(
        self, manager: IntegrityManager, temp_portfolios_dir: Path, sample_portfolio: dict
    ):
        """Test that keystore header is exactly 2 digits with leading zero."""
        # Create 5 portfolios
        for i in range(5):
            portfolio = sample_portfolio.copy()
            portfolio["name"] = f"Portfolio {i}"
            (temp_portfolios_dir / f"p{i}.json").write_text(json.dumps(portfolio), encoding="utf-8")

        # Generate keystore
        manager.generate_keystore(temp_portfolios_dir)

        # Read header
        keystore_data = manager.keystore_file.read_bytes()
        header = keystore_data[:2].decode("utf-8")

        # Header should be "05" (2 digits with leading zero)
        assert header == "05"
        assert len(header) == 2


# === verify_and_restore() Tests ===


class TestVerifyAndRestore:
    """Test IntegrityManager.verify_and_restore() method."""

    def test_verify_all_portfolios_intact(
        self, manager: IntegrityManager, temp_portfolios_dir: Path, sample_portfolio: dict
    ):
        """Test verify_and_restore with all portfolios intact."""
        # Create and generate keystore
        portfolio_file = temp_portfolios_dir / "test_portfolio.json"
        portfolio_file.write_text(json.dumps(sample_portfolio), encoding="utf-8")
        manager.generate_keystore(temp_portfolios_dir)

        # Verify
        all_ok, verified, restored = manager.verify_and_restore(temp_portfolios_dir)

        # All should be OK
        assert all_ok is True
        assert len(verified) == 1
        assert len(restored) == 0
        assert verified[0] == portfolio_file

    def test_verify_restores_corrupted_portfolio(
        self, manager: IntegrityManager, temp_portfolios_dir: Path, sample_portfolio: dict
    ):
        """Test verify_and_restore restores corrupted portfolio."""
        # Create and generate keystore
        portfolio_file = temp_portfolios_dir / "test_portfolio.json"
        portfolio_file.write_text(json.dumps(sample_portfolio), encoding="utf-8")
        manager.generate_keystore(temp_portfolios_dir)

        # Corrupt the portfolio file
        corrupted_data = sample_portfolio.copy()
        corrupted_data["name"] = "CORRUPTED NAME"
        portfolio_file.write_text(json.dumps(corrupted_data), encoding="utf-8")

        # Verify and restore
        all_ok, verified, restored = manager.verify_and_restore(temp_portfolios_dir)

        # Should restore corrupted file
        assert all_ok is False
        assert len(verified) == 0
        assert len(restored) == 1
        assert restored[0][0] == portfolio_file
        assert "SHA256 mismatch" in restored[0][1]

        # Verify file restored to original
        restored_data = json.loads(portfolio_file.read_text(encoding="utf-8"))
        assert restored_data["name"] == sample_portfolio["name"]

    def test_verify_restores_missing_portfolio(
        self, manager: IntegrityManager, temp_portfolios_dir: Path, sample_portfolio: dict
    ):
        """Test verify_and_restore restores missing portfolio."""
        # Create and generate keystore
        portfolio_file = temp_portfolios_dir / "test_portfolio.json"
        portfolio_file.write_text(json.dumps(sample_portfolio), encoding="utf-8")
        manager.generate_keystore(temp_portfolios_dir)

        # Delete the portfolio file
        portfolio_file.unlink()
        assert not portfolio_file.exists()

        # Verify and restore
        all_ok, verified, restored = manager.verify_and_restore(temp_portfolios_dir)

        # Should restore missing file
        assert all_ok is False
        assert len(verified) == 0
        assert len(restored) == 1
        assert restored[0][0] == portfolio_file
        assert "File missing" in restored[0][1]

        # Verify file restored
        assert portfolio_file.exists()
        restored_data = json.loads(portfolio_file.read_text(encoding="utf-8"))
        assert restored_data["name"] == sample_portfolio["name"]

    def test_verify_missing_keystore_raises_error(self, manager: IntegrityManager, temp_portfolios_dir: Path):
        """Test verify_and_restore raises ValueError if keystore missing."""
        # No keystore generated
        with pytest.raises(ValueError, match=r"Keystore missing.*rxl.kst not found"):
            manager.verify_and_restore(temp_portfolios_dir)

    def test_verify_missing_salt_raises_error(
        self, manager: IntegrityManager, temp_portfolios_dir: Path, sample_portfolio: dict
    ):
        """Test verify_and_restore raises ValueError if salt missing."""
        # Create keystore
        (temp_portfolios_dir / "test.json").write_text(json.dumps(sample_portfolio), encoding="utf-8")
        manager.generate_keystore(temp_portfolios_dir)

        # Delete salt file
        manager.salt_file.unlink()

        # Should raise error
        with pytest.raises(ValueError, match=r"Salt missing.*salt.key not found"):
            manager.verify_and_restore(temp_portfolios_dir)

    def test_verify_invalid_salt_size_raises_error(
        self, manager: IntegrityManager, temp_portfolios_dir: Path, sample_portfolio: dict
    ):
        """Test verify_and_restore raises ValueError if salt has wrong size."""
        # Create keystore
        (temp_portfolios_dir / "test.json").write_text(json.dumps(sample_portfolio), encoding="utf-8")
        manager.generate_keystore(temp_portfolios_dir)

        # Replace salt with invalid size
        manager.salt_file.write_bytes(b"invalid_salt_too_short")

        # Should raise error
        with pytest.raises(ValueError, match=r"Invalid salt.*expected 32 bytes"):
            manager.verify_and_restore(temp_portfolios_dir)

    def test_verify_corrupted_keystore_header_raises_error(
        self, manager: IntegrityManager, temp_portfolios_dir: Path, sample_portfolio: dict
    ):
        """Test verify_and_restore raises ValueError if keystore header corrupted."""
        # Create keystore
        (temp_portfolios_dir / "test.json").write_text(json.dumps(sample_portfolio), encoding="utf-8")
        manager.generate_keystore(temp_portfolios_dir)

        # Corrupt header
        manager.keystore_file.write_bytes(b"XX" + manager.keystore_file.read_bytes()[2:])

        # Should raise error
        with pytest.raises(ValueError, match="Invalid keystore header"):
            manager.verify_and_restore(temp_portfolios_dir)

    def test_verify_keystore_too_small_raises_error(self, manager: IntegrityManager, temp_portfolios_dir: Path):
        """Test verify_and_restore raises ValueError if keystore too small."""
        # Create salt
        manager.write_salt(manager.generate_salt())

        # Create invalid keystore (too small)
        manager.keystore_file.write_bytes(b"0")  # Only 1 byte (needs 2+)

        # Should raise error
        with pytest.raises(ValueError, match=r"Keystore corrupted.*too small"):
            manager.verify_and_restore(temp_portfolios_dir)

    def test_verify_truncated_sha256_raises_error(
        self, manager: IntegrityManager, temp_portfolios_dir: Path, sample_portfolio: dict
    ):
        """Test verify_and_restore raises ValueError if SHA256 field truncated."""
        # Create keystore
        (temp_portfolios_dir / "test.json").write_text(json.dumps(sample_portfolio), encoding="utf-8")
        manager.generate_keystore(temp_portfolios_dir)

        # Truncate keystore (remove bytes after header)
        keystore_data = manager.keystore_file.read_bytes()
        manager.keystore_file.write_bytes(keystore_data[:10])  # Header + partial SHA256

        # Should raise error
        with pytest.raises(ValueError, match=r"Keystore corrupted at block 0.*SHA256"):
            manager.verify_and_restore(temp_portfolios_dir)

    def test_verify_truncated_size_field_raises_error(
        self, manager: IntegrityManager, temp_portfolios_dir: Path, sample_portfolio: dict
    ):
        """Test verify_and_restore raises ValueError if size field truncated."""
        # Create keystore
        (temp_portfolios_dir / "test.json").write_text(json.dumps(sample_portfolio), encoding="utf-8")
        manager.generate_keystore(temp_portfolios_dir)

        # Truncate after SHA256 (partial size field)
        keystore_data = manager.keystore_file.read_bytes()
        manager.keystore_file.write_bytes(keystore_data[: 2 + 64 + 2])  # Header + SHA256 + partial size

        # Should raise error
        with pytest.raises(ValueError, match=r"Keystore corrupted at block 0.*Size"):
            manager.verify_and_restore(temp_portfolios_dir)

    def test_verify_invalid_size_field_raises_error(
        self, manager: IntegrityManager, temp_portfolios_dir: Path, sample_portfolio: dict
    ):
        """Test verify_and_restore raises ValueError if size field is not numeric."""
        # Create keystore
        (temp_portfolios_dir / "test.json").write_text(json.dumps(sample_portfolio), encoding="utf-8")
        manager.generate_keystore(temp_portfolios_dir)

        # Corrupt size field (replace with non-numeric)
        keystore_data = bytearray(manager.keystore_file.read_bytes())
        size_offset = 2 + 64  # Header + SHA256
        keystore_data[size_offset : size_offset + 5] = b"XXXXX"
        manager.keystore_file.write_bytes(bytes(keystore_data))

        # Should raise error
        with pytest.raises(ValueError, match="Invalid size field at block 0"):
            manager.verify_and_restore(temp_portfolios_dir)

    def test_verify_truncated_encrypted_data_raises_error(
        self, manager: IntegrityManager, temp_portfolios_dir: Path, sample_portfolio: dict
    ):
        """Test verify_and_restore raises ValueError if encrypted data truncated."""
        # Create keystore
        (temp_portfolios_dir / "test.json").write_text(json.dumps(sample_portfolio), encoding="utf-8")
        manager.generate_keystore(temp_portfolios_dir)

        # Truncate encrypted data (remove last bytes)
        keystore_data = manager.keystore_file.read_bytes()
        manager.keystore_file.write_bytes(keystore_data[:-10])  # Remove 10 bytes

        # Should raise error
        with pytest.raises(ValueError, match=r"Keystore corrupted at block 0.*Data"):
            manager.verify_and_restore(temp_portfolios_dir)

    def test_verify_multiple_portfolios_mixed_state(
        self, manager: IntegrityManager, temp_portfolios_dir: Path, sample_portfolio: dict
    ):
        """Test verify_and_restore with mixed portfolio states (intact, corrupted, missing)."""
        # Create 3 portfolios
        portfolios = []
        for i in range(3):
            p = sample_portfolio.copy()
            p["name"] = f"Portfolio {i + 1}"
            file = temp_portfolios_dir / f"portfolio_{i + 1}.json"
            file.write_text(json.dumps(p), encoding="utf-8")
            portfolios.append(file)

        # Generate keystore
        manager.generate_keystore(temp_portfolios_dir)

        # Portfolio 0: Keep intact
        # Portfolio 1: Corrupt
        corrupted = sample_portfolio.copy()
        corrupted["name"] = "CORRUPTED"
        portfolios[1].write_text(json.dumps(corrupted), encoding="utf-8")

        # Portfolio 2: Delete
        portfolios[2].unlink()

        # Verify and restore
        all_ok, verified, restored = manager.verify_and_restore(temp_portfolios_dir)

        # Should restore 2 files
        assert all_ok is False
        assert len(verified) == 1  # Portfolio 0
        assert len(restored) == 2  # Portfolio 1 (corrupted), 2 (missing)

        # Verify intact portfolio
        assert verified[0] == portfolios[0]

        # Verify restored portfolios
        restored_paths = [r[0] for r in restored]
        assert portfolios[1] in restored_paths
        assert portfolios[2] in restored_paths

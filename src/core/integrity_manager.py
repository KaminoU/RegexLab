"""
Integrity Manager for RegexLab builtin portfolios protection.

Multi-Portfolio Integrity System (v2).
"""

from __future__ import annotations

import hashlib
import itertools
import json
import secrets
from pathlib import Path

from .helpers import normalize_portfolio_name
from .logger import get_logger


class IntegrityManager:
    """Manages multi-portfolio builtin integrity protection."""

    SALT_SIZE = 32
    SHA256_SIZE = 64
    SIZE_FIELD_LENGTH = 5
    HEADER_LENGTH = 2
    PBKDF2_ITERATIONS = 100000

    def __init__(self, regexlab_dir: Path) -> None:
        self.regexlab_dir = regexlab_dir
        self.salt_file = regexlab_dir / "salt.key"
        self.keystore_file = regexlab_dir / "rxl.kst"
        self.logger = get_logger()

    # === Salt Management ===

    def generate_salt(self) -> bytes:
        """Generate cryptographic random salt."""
        return secrets.token_bytes(self.SALT_SIZE)

    def read_salt(self) -> bytes | None:
        """Read salt from salt.key file."""
        if not self.salt_file.exists():
            return None
        return self.salt_file.read_bytes()

    def write_salt(self, salt: bytes) -> None:
        """Write salt to salt.key file."""
        self.regexlab_dir.mkdir(parents=True, exist_ok=True)
        self.salt_file.write_bytes(salt)
        self.logger.info("✓ salt.key created (%s bytes)", len(salt))

    # === Key Derivation ===

    def derive_key(self, salt: bytes, context: str) -> bytes:
        """
        Derive unique encryption key using PBKDF2 + portfolio SHA256.

        Args:
            salt: Master salt from salt.key
            context: Portfolio SHA256 (hex string)

        Returns:
            32-byte derived key
        """
        password = salt + context.encode("utf-8")
        return hashlib.pbkdf2_hmac(
            hash_name="sha256", password=password, salt=salt, iterations=self.PBKDF2_ITERATIONS, dklen=32
        )

    # === Encryption ===

    def xor_encrypt(self, data: bytes, key: bytes) -> bytes:
        """Encrypt data using XOR with key (symmetric operation)."""
        return bytes(a ^ b for a, b in zip(data, itertools.cycle(key)))

    def xor_decrypt(self, data: bytes, key: bytes) -> bytes:
        """Decrypt data (XOR is symmetric)."""
        return self.xor_encrypt(data, key)

    # === SHA256 Hashing ===

    def compute_sha256(self, data: bytes) -> str:
        """Compute SHA256 hash of data."""
        return hashlib.sha256(data).hexdigest()

    # === Portfolio Block Management ===

    def create_portfolio_block(self, salt: bytes, portfolio_json: str) -> tuple[str, bytes]:
        """
        Create encrypted block for one portfolio.

        Args:
            salt: Master salt
            portfolio_json: Portfolio JSON string

        Returns:
            Tuple of (sha256, encrypted_data)
        """
        portfolio_bytes = portfolio_json.encode("utf-8")
        sha256 = self.compute_sha256(portfolio_bytes)
        key = self.derive_key(salt, context=sha256)
        encrypted = self.xor_encrypt(portfolio_bytes, key)
        self.logger.debug("Created block: SHA256=%s... size=%s bytes", sha256[:16], len(encrypted))
        return sha256, encrypted

    def decrypt_portfolio_block(self, salt: bytes, sha256: str, encrypted_data: bytes) -> str:
        """
        Decrypt one portfolio block.

        Args:
            salt: Master salt
            sha256: Stored SHA256
            encrypted_data: Encrypted portfolio data

        Returns:
            Decrypted JSON string

        Raises:
            ValueError: If decryption fails or SHA256 mismatch
        """
        key = self.derive_key(salt, context=sha256)
        decrypted = self.xor_decrypt(encrypted_data, key)
        computed_sha256 = self.compute_sha256(decrypted)
        if computed_sha256 != sha256:
            raise ValueError(f"SHA256 mismatch: expected {sha256[:16]}..., got {computed_sha256[:16]}...")
        return decrypted.decode("utf-8")

    # === Multi-Portfolio Keystore ===

    def generate_keystore(self, portfolios_dir: Path) -> tuple[int, int]:
        """
        Generate rxl.kst from all portfolios in builtin directory.

        Args:
            portfolios_dir: Path to builtin portfolios directory

        Returns:
            Tuple of (portfolios_count, total_bytes)

        Raises:
            IOError: If unable to read/write files
            ValueError: If portfolio validation fails
        """
        self.logger.info("Generating keystore from: %s", portfolios_dir)

        # 1. Scan portfolio files
        portfolio_files = sorted(portfolios_dir.glob("*.json"))
        if not portfolio_files:
            raise ValueError(f"No portfolio files found in {portfolios_dir}")

        if len(portfolio_files) > 99:
            raise ValueError(f"Too many portfolios: {len(portfolio_files)} (max 99)")

        self.logger.info("Found %s portfolio files", len(portfolio_files))

        # 2. Read or generate salt
        salt = self.read_salt()
        if salt is None:
            self.logger.info("Generating new salt...")
            salt = self.generate_salt()
            self.write_salt(salt)
        else:
            self.logger.debug("Using existing salt")

        # 3. Build keystore data
        blocks: list[tuple[str, bytes]] = []

        for portfolio_file in portfolio_files:
            self.logger.debug("Processing: %s", portfolio_file.name)

            # Read portfolio
            portfolio_json = portfolio_file.read_text(encoding="utf-8")

            # Validate JSON
            try:
                json.loads(portfolio_json)
            except json.JSONDecodeError as e:
                raise ValueError(f"Invalid JSON in {portfolio_file.name}: {e}") from e

            # Create encrypted block
            sha256, encrypted = self.create_portfolio_block(salt, portfolio_json)
            blocks.append((sha256, encrypted))

        # 4. Write rxl.kst
        self.regexlab_dir.mkdir(parents=True, exist_ok=True)

        # Header: 2-digit portfolio count
        header = f"{len(blocks):02d}".encode()
        keystore_data = header

        # Add each block: SHA256 (64) + Size (5) + Data (variable)
        for sha256, encrypted in blocks:
            size_str = f"{len(encrypted):05d}".encode()
            block_data = sha256.encode("utf-8") + size_str + encrypted
            keystore_data += block_data

        self.keystore_file.write_bytes(keystore_data)
        total_size = len(keystore_data)

        self.logger.info("✓ rxl.kst created: %s portfolios, %s bytes", len(blocks), total_size)

        return len(blocks), total_size

    def verify_and_restore(self, portfolios_dir: Path) -> tuple[bool, list[Path], list[tuple[Path, str]]]:
        """
        Verify all builtin portfolios and restore corrupted ones.

        Args:
            portfolios_dir: Path to builtin portfolios directory

        Returns:
            Tuple of (all_ok, verified_files, restored_files)
            - all_ok: True if all portfolios are intact
            - verified_files: List of verified portfolio paths
            - restored_files: List of (path, reason) tuples

        Raises:
            IOError: If unable to read keystore or write restored files
            ValueError: If keystore format invalid
        """
        self.logger.info("Verifying builtin portfolios integrity...")

        # 1. Check keystore exists
        if not self.keystore_file.exists():
            raise ValueError("Keystore missing (rxl.kst not found)")

        if not self.salt_file.exists():
            raise ValueError("Salt missing (salt.key not found)")

        # 2. Read salt
        salt = self.read_salt()
        if salt is None or len(salt) != self.SALT_SIZE:
            raise ValueError(f"Invalid salt (expected {self.SALT_SIZE} bytes)")

        # 3. Parse rxl.kst
        keystore_data = self.keystore_file.read_bytes()

        if len(keystore_data) < self.HEADER_LENGTH:
            raise ValueError("Keystore corrupted (too small)")

        # Read header
        header = keystore_data[: self.HEADER_LENGTH].decode("utf-8")
        try:
            portfolio_count = int(header)
        except ValueError as exc:
            raise ValueError(f"Invalid keystore header: {header}") from exc

        self.logger.info("Keystore contains %s portfolios", portfolio_count)

        # 4. Parse blocks
        verified_files: list[Path] = []
        restored_files: list[tuple[Path, str]] = []
        cursor = self.HEADER_LENGTH

        for i in range(portfolio_count):
            # Read SHA256 (64 chars)
            if cursor + self.SHA256_SIZE > len(keystore_data):
                raise ValueError(f"Keystore corrupted at block {i} (SHA256)")

            sha256 = keystore_data[cursor : cursor + self.SHA256_SIZE].decode("utf-8")
            cursor += self.SHA256_SIZE

            # Read Size (5 chars)
            if cursor + self.SIZE_FIELD_LENGTH > len(keystore_data):
                raise ValueError(f"Keystore corrupted at block {i} (Size)")

            size_str = keystore_data[cursor : cursor + self.SIZE_FIELD_LENGTH].decode("utf-8")
            try:
                encrypted_size = int(size_str)
            except ValueError as exc:
                raise ValueError(f"Invalid size field at block {i}: {size_str}") from exc

            cursor += self.SIZE_FIELD_LENGTH

            # Read encrypted data
            if cursor + encrypted_size > len(keystore_data):
                raise ValueError(f"Keystore corrupted at block {i} (Data)")

            encrypted_data = keystore_data[cursor : cursor + encrypted_size]
            cursor += encrypted_size

            # Decrypt and verify
            try:
                decrypted_json = self.decrypt_portfolio_block(salt, sha256, encrypted_data)
            except ValueError as e:
                self.logger.error("Block %s decryption failed: %s", i, e)
                raise ValueError(f"Block {i} decryption failed: {e}") from e

            # Parse JSON to get portfolio name
            try:
                portfolio_data = json.loads(decrypted_json)
                portfolio_name = portfolio_data.get("name", f"Unknown_{i}")
            except json.JSONDecodeError as e:
                raise ValueError(f"Block {i} invalid JSON: {e}") from e

            # Determine file path
            filename = normalize_portfolio_name(portfolio_name)
            portfolio_file = portfolios_dir / filename

            # Compare with disk
            if portfolio_file.exists():
                current_json = portfolio_file.read_text(encoding="utf-8")
                current_sha256 = self.compute_sha256(current_json.encode("utf-8"))

                if current_sha256 == sha256:
                    # OK
                    verified_files.append(portfolio_file)
                    self.logger.debug("✓ %s - intact", filename)
                else:
                    # CORRUPTED - Restore
                    portfolio_file.write_text(decrypted_json, encoding="utf-8")
                    restored_files.append((portfolio_file, "SHA256 mismatch (file modified)"))
                    self.logger.warning("⚠ %s - RESTORED (corrupted)", filename)
            else:
                # MISSING - Restore
                portfolio_file.write_text(decrypted_json, encoding="utf-8")
                restored_files.append((portfolio_file, "File missing"))
                self.logger.warning("⚠ %s - RESTORED (missing)", filename)

        all_ok = len(restored_files) == 0

        if all_ok:
            self.logger.info("✓ All %s portfolios verified OK", len(verified_files))
        else:
            self.logger.warning("⚠ Restored %s portfolios, %s verified OK", len(restored_files), len(verified_files))

        return all_ok, verified_files, restored_files

"""
Private command to generate integrity keystore for builtin portfolios.

Multi-Portfolio Integrity System (v2):
- Scans all *.json files in data/portfolios/
- Generates one rxl.kst containing all builtin portfolios
- Each portfolio gets unique encryption key

This command is NOT exposed in the Command Palette.
Run manually from Python console when builtin portfolios are finalized.
"""

from __future__ import annotations

from pathlib import Path

import sublime  # pyright: ignore[reportMissingImports]
import sublime_plugin  # pyright: ignore[reportMissingImports]

from ..core.integrity_manager import IntegrityManager
from ..core.logger import get_logger


class RegexlabGenerateIntegrityCommand(sublime_plugin.ApplicationCommand):  # type: ignore[misc]
    """
    Private command to generate integrity files for builtin portfolios.

    Usage from Sublime Text console:
        sublime.run_command("regexlab_generate_integrity")

    This will:
    1. Scan all *.json files in data/portfolios/
    2. Generate salt.key (or reuse existing)
    3. Create rxl.kst with encrypted backups (one block per portfolio)
    """

    def run(self) -> None:
        """Execute the command."""
        logger = get_logger()
        logger.info("=" * 60)
        logger.info("GENERATING MULTI-PORTFOLIO INTEGRITY KEYSTORE (v2)")
        logger.info("=" * 60)

        try:
            # Paths
            packages_path = Path(sublime.packages_path())
            builtin_portfolios_dir = packages_path / "RegexLab" / "data" / "portfolios"
            regexlab_dir = packages_path / "RegexLab" / "data" / ".regexlab"  # BUILTIN location!

            # Check if builtin portfolios directory exists
            if not builtin_portfolios_dir.exists():
                logger.error("✗ Builtin portfolios directory not found: %s", builtin_portfolios_dir)
                sublime.error_message(
                    "RegexLab: Builtin portfolios directory not found!\n\n"
                    f"Expected: {builtin_portfolios_dir}\n\n"
                    "Cannot generate integrity files."
                )
                return

            # List portfolio files
            portfolio_files = sorted(builtin_portfolios_dir.glob("*.json"))
            if not portfolio_files:
                logger.error("✗ No portfolio files found in: %s", builtin_portfolios_dir)
                sublime.error_message(
                    "RegexLab: No portfolio files found!\n\n"
                    f"Directory: {builtin_portfolios_dir}\n\n"
                    "Add at least one .json portfolio file."
                )
                return

            logger.info("Found %s portfolio files:", len(portfolio_files))
            for pf in portfolio_files:
                logger.info("  - %s", pf.name)

            # Create integrity manager
            manager = IntegrityManager(regexlab_dir)

            # Check if keystore already exists
            if manager.keystore_file.exists() or manager.salt_file.exists():
                logger.warning("⚠ Integrity files already exist!")
                logger.warning("  salt.key: %s", "EXISTS" if manager.salt_file.exists() else "missing")
                logger.warning("  rxl.kst: %s", "EXISTS" if manager.keystore_file.exists() else "missing")

                # Ask user confirmation
                result = sublime.yes_no_cancel_dialog(
                    "RegexLab: Integrity files already exist!\n\n"
                    "Regenerating will update the keystore with current portfolios.\n\n"
                    "Do you want to continue?",
                    "Regenerate",
                    "Cancel",
                )

                if result != sublime.DIALOG_YES:
                    logger.info("✗ Operation cancelled by user")
                    return

            # Generate keystore
            logger.info("Generating integrity keystore...")
            portfolio_count, total_bytes = manager.generate_keystore(builtin_portfolios_dir)

            # Success
            logger.info("=" * 60)
            logger.info("SUCCESS: Integrity keystore generated!")
            logger.info("  Location: %s", regexlab_dir)
            logger.info("  Portfolios: %s", portfolio_count)
            logger.info("  Total size: %s bytes", f"{total_bytes:,}")
            logger.info("  Files:")
            logger.info("    - salt.key (%s bytes)", manager.salt_file.stat().st_size)
            logger.info("    - rxl.kst (%s bytes)", f"{manager.keystore_file.stat().st_size:,}")
            logger.info("=" * 60)

            sublime.message_dialog(
                "RegexLab: Integrity keystore generated successfully!\n\n"
                f"Location: {regexlab_dir}\n\n"
                f"Portfolios protected: {portfolio_count}\n"
                f"Total size: {total_bytes:,} bytes\n\n"
                "Files created:\n"
                f"  • salt.key ({manager.salt_file.stat().st_size} bytes)\n"
                f"  • rxl.kst ({manager.keystore_file.stat().st_size:,} bytes)\n\n"
                "Builtin portfolios are now protected."
            )

        except ValueError as e:
            logger.error("✗ Validation error: %s", e)
            import traceback

            logger.error("Traceback: %s", traceback.format_exc())
            sublime.error_message(f"RegexLab: Keystore generation failed!\n\n{e}\n\nCheck console for details.")

        except OSError as e:
            logger.error("✗ I/O error: %s", e)
            import traceback

            logger.error("Traceback: %s", traceback.format_exc())
            sublime.error_message(f"RegexLab: File operation failed!\n\n{e}\n\nCheck console for details.")

    def is_visible(self) -> bool:
        """Hide from Command Palette."""
        return False

    def description(self) -> str:
        """Command description."""
        return "Generate integrity keystore for RegexLab builtin portfolios (PRIVATE)"

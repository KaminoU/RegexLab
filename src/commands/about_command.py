"""
About Command - Display RegexLab version and information.

Shows installation message and version details in a new buffer.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import sublime  # pyright: ignore[reportMissingImports]


class RegexlabAboutCommand:
    """
    Display RegexLab version and about information.

    Opens the install.txt message in a new buffer for easy reference.
    """

    def run(self, window: sublime.Window) -> None:
        """
        Execute the About command.

        Args:
            window: Sublime Text window instance
        """
        import sublime  # pyright: ignore[reportMissingImports]

        # Get RegexLab package path
        packages_path = Path(sublime.packages_path())
        regexlab_path = packages_path / "RegexLab"
        install_msg_path = regexlab_path / "messages" / "install.txt"

        # Read install message
        try:
            content = install_msg_path.read_text(encoding="utf-8")
        except FileNotFoundError:
            # Fallback if install.txt doesn't exist
            content = self._get_fallback_about()

        # Create new buffer and display
        view = window.new_file()
        view.set_name("About RegexLab")
        view.set_scratch(True)  # Don't prompt to save
        view.set_read_only(False)
        view.run_command("append", {"characters": content})
        view.set_read_only(True)

        # Set syntax to plain text for better readability
        view.assign_syntax("Packages/Text/Plain text.tmLanguage")

    def _get_fallback_about(self) -> str:
        """
        Fallback about message if install.txt is missing.

        Returns:
            str: About message
        """
        return """
╔══════════════════════════════════════════════════════════════════════════════╗
║                                                                              ║
║                       🎯 RegexLab - About 🎯                                ║
║                                                                              ║
║            The Ultimate Regex Pattern Manager for Sublime Text              ║
║                                                                              ║
╚══════════════════════════════════════════════════════════════════════════════╝

RegexLab transforms how you work with regex patterns in Sublime Text.

📖 Documentation: https://github.com/KaminoU/RegexLab/blob/main/README.md
🐛 Issues/Bugs: https://github.com/KaminoU/RegexLab/issues
⭐ GitHub: https://github.com/KaminoU/RegexLab

═══════════════════════════════════════════════════════════════════════════════

🔧 QUICK START:

  1. Ctrl+K, Ctrl+R → Load Pattern
  2. Ctrl+K, Ctrl+P → Portfolio Manager
  3. Ctrl+K, Ctrl+U → Use Selection

═══════════════════════════════════════════════════════════════════════════════

Enjoy! 🎉
"""

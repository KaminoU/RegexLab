# Contributing to RegexLab

Hey! Thanks for wanting to make RegexLab better! Whether you're fixing a typo, squashing a bug, or adding a cool feature, we appreciate your help. 🎉

This guide will get you up and running quickly.

---

## Table of Contents

- [Quick Start](#quick-start)
- [Development Setup](#development-setup)
- [Code Quality](#code-quality)
- [Testing](#testing)
- [Submitting Changes](#submitting-changes)
- [CI/CD](#cicd-pipeline)
- [Need Help?](#need-help)

---

## Quick Start

### What you'll need

- **Sublime Text 4** (Build 4050+)
- **Python 3.8+** for testing
- **Git** for version control

### Fork and clone

```bash
# Fork the repo on GitHub, then:
git clone https://github.com/YOUR_USERNAME/RegexLab.git
cd RegexLab

# Add upstream remote
git remote add upstream https://github.com/KaminoU/RegexLab.git
```

### Branching

- `main` → Stable releases only
- `DEV` → Where the magic happens
- `feature/*` → New features
- `fix/*` → Bug fixes

```bash
# Start working on something
git checkout DEV
git pull upstream DEV
git checkout -b feature/cool-new-thing
```

---

## Development Setup

### Install dev tools

We use **tox** to make testing easy across Python versions:

```bash
# Option 1: Install tox (recommended)
pip install tox

# Option 2: Install tools manually
pip install pytest pytest-cov ruff mypy
```

> **Note**: RegexLab supports **Python 3.8 through 3.13**. All tests must pass on both Python 3.8 and 3.13 to ensure compatibility with current and future Sublime Text versions.

### Project structure

```
RegexLab/
├── src/                   # Source code
│   ├── commands/          # Sublime Text commands
│   ├── core/              # Core logic
│   └── services/          # Business services
├── tests/                 # Tests
│   ├── unit/              # Unit tests (pytest)
│   └── ui/                # UI tests (UnitTesting in ST4)
├── data/                  # Plugin data
│   ├── portfolios/        # Built-in portfolios
│   └── .regexlab/         # Integrity checksums
└── RegexLab.py            # Plugin entry point
```

---

## Code Quality

We keep the code clean and consistent. Here's what we check:

### 1. Linting & formatting (Ruff)

Fast and opinionated Python linter:

```bash
ruff check src/ tests/       # Check for issues
ruff format src/ tests/      # Auto-format
```

### 2. Type checking (mypy)

We enforce type hints (strict mode):

```bash
mypy src/ --ignore-missing-imports --strict
```

### 3. Code style

- ✅ Type hints on all functions
- ✅ Docstrings for public APIs (Google style)
- ✅ Descriptive variable names
- ✅ Small, focused functions
- ✅ English naming and comments

**Example:**

```python
def load_portfolio(path: Path, readonly: bool = False) -> Portfolio:
    """
    Load a portfolio from a JSON file.

    Args:
        path: Path to the portfolio JSON
        readonly: Mark as builtin (read-only)

    Returns:
        Loaded Portfolio object

    Raises:
        FileNotFoundError: Portfolio file not found
        ValueError: Invalid JSON format
    """
    ...
```

---

## Testing

### Run tests

```bash
# Using tox (tests all Python versions + quality checks)
tox

# Quick dev tests (current Python only)
pytest tests/ -v

# With coverage
pytest tests/ --cov=src --cov-report=html

# Specific test
pytest tests/unit/test_models.py -v
```

### Coverage targets

We aim for high coverage on critical code:

- **Core modules** (models, engine): **95%+**
- **Utilities** (helpers, logger): **65%+**
- **Commands** (UI layer): **50%+**

**Current coverage**: 93% core, 498 tests passing ✅

### Writing tests

```python
def test_portfolio_rejects_missing_name():
    """Should reject portfolios without a name."""
    invalid = {"description": "Test", "patterns": []}

    with pytest.raises(ValueError, match="Missing required field"):
        Portfolio.from_dict(invalid)
```

---

## Submitting Changes

### Before you submit

1. **Run quality checks:**
   ```bash
   tox  # This runs everything: lint, typecheck, tests
   ```

2. **Make sure tests pass**
3. **Update docs if needed**
4. **Write a clear commit message**

### Commit messages

```
<type>: <short description>

<optional details>
```

**Types:** `feat`, `fix`, `docs`, `test`, `refactor`, `chore`

**Examples:**
```
feat: add auto-discovery for portfolios

Scans portfolios/ directory on startup and loads all .json files.

Closes #42
```

```
fix: handle missing keystore gracefully

Shows user-friendly error instead of crashing.
```

### Pull request

1. **Push your branch:**
   ```bash
   git push origin feature/cool-new-thing
   ```

2. **Open PR on GitHub:**
   - Target: `DEV` (not `main`)
   - Fill in the template
   - Link related issues

3. **PR checklist:**
   - [ ] All CI checks green
   - [ ] Tests added
   - [ ] Docs updated
   - [ ] No conflicts with `DEV`

---

## CI/CD Pipeline

GitHub Actions runs on every push/PR:

- **Lint** (ruff)
- **Type check** (mypy strict)
- **Tests** (pytest)
- **Coverage** report

**Tested on:**
- Python 3.8 & 3.13
- Ubuntu, Windows, macOS

Check the "Actions" tab to see results.

---

## Need Help?

- **Bug?** Open an issue with steps to reproduce
- **Feature idea?** Open an issue describing the use case
- **Question?** Open a discussion or issue

---

Thanks for contributing! 🚀

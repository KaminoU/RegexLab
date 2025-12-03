# Changelog

All notable changes to RegexLab will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [1.1.0] - 2025-12-03

### Fixed

- Fix integrity check failure when running as a `.sublime-package` (packaged mode). Resources are now correctly extracted to `User/RegexLab/` to allow integrity verification.
- Fix patterns being trimmed of trailing spaces when adding or editing them.

---

## [1.0.0] - 2025-10-29

Initial public release.

### Added

#### Core Features

- Multi-portfolio management system with auto-discovery
- Portfolio Manager UI with keyboard shortcuts
- New Portfolio Wizard for creating custom portfolios
- Portfolio enable/disable functionality
- Static and dynamic pattern support
- Dynamic variables: `{date}`, `{time}`, `{username}`, `{clipboard}`
- Pattern resolution engine with variable substitution
- Find panel injection for seamless integration

#### Security & Integrity

- Multi-portfolio integrity protection system
- Encrypted backup for all builtin portfolios
- Auto-restore on corruption detection
- Per-portfolio isolation with unique encryption keys
- PBKDF2-HMAC-SHA256 key derivation (100,000 iterations)

#### Testing & Quality Assurance

- Comprehensive test suite (492 core tests, 6 UI tests)
- 93% core coverage on critical modules
- UI testing framework with UnitTesting plugin
- Cross-platform validation (Windows, Linux, macOS)
- Python 3.8-3.13 compatibility
- CI/CD pipeline with tox automation

#### Performance Optimizations

- Cached property for pattern variables (333x speedup)
- Pre-compiled regex patterns (13x speedup on resolution)
- O(1) variable lookup after first access
- Zero runtime compilation overhead

#### Developer Experience

- Complete tox configuration for multi-version testing
- HTML coverage reports
- Automated linting with ruff
- Strict type checking with mypy
- Comprehensive documentation

### Changed

- Complete rewrite for Sublime Text 4
- Migrated from RegexPortfolio (ST3) architecture
- Enhanced error handling and logging system
- Improved UI with grouped pattern display
- Dependabot interval set to monthly updates

### Fixed

- OOM protection for large clipboard content (>10MB limit)
- Cross-platform CI/CD compatibility issues
- Defensive window validation in timer chains
- Portfolio validation error handling
- Type checking errors across Python 3.8-3.13

### Documentation

- Complete README with usage examples and performance metrics
- Contributing guidelines with friendly tone
- Issue and pull request templates
- Scripts documentation for WSL2/headless testing
- Portfolio schema and creation guide
- Integrity system technical documentation

### Performance Benchmarks

- Pattern.variables: 3.33µs (cached) vs 1.11ms (baseline) - 333x faster
- Pattern.resolve(): 76.9µs vs 1ms (baseline) - 13x faster
- CCode audit score: 9.8/10 (production-ready)

### Tested Environments

- Windows 11 (Python 3.8.20, 3.13.7)
- Linux WSL2 Ubuntu 22.04 (Python 3.8, 3.13)
- macOS (Python 3.8, 3.13)
- Sublime Text 4 (Build 4050+)

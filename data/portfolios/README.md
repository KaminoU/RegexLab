# 📁 RegexLab Portfolios Directory

This directory contains **built-in portfolios** for RegexLab. Each portfolio is a JSON file containing a collection of regex patterns.

## 🤔 What's a portfolio?

A portfolio is a JSON file that groups related regex patterns together. Each portfolio has:
- **Metadata**: name, author, version, description, creation date
- **Patterns**: Collection of static or dynamic regex patterns
- **Readonly flag**: Builtin portfolios are readonly (can't be modified in UI)

## 🔧 How portfolios are loaded (Auto-Discovery)

### Auto-loaded portfolios

RegexLab scans and loads **all `.json` files** from these locations at startup:

1. **Built-in Portfolios** (this directory):
   ```
   RegexLab/data/portfolios/*.json  → Always loaded
   ```
   - Official RegexLab patterns
   - Readonly and integrity-protected
   - Cannot be disabled

2. **Custom Active Portfolios**:
   ```
   User/RegexLab/portfolios/*.json  → Auto-loaded
   ```
   - Your custom portfolios
   - Editable and manageable
   - Enable/disable via Portfolio Manager

3. **Disabled Portfolios** (not loaded):
   ```
   User/RegexLab/disabled_portfolios/*.json  → Ignored
   ```
   - Portfolios you want to keep but not load
   - Move here to disable without deleting
   - Move back to `portfolios/` to re-enable

### Why auto-discovery?

- **Simplicity**: No configuration needed - just drop files in folders
- **Visual**: See active/disabled portfolios in file explorer
- **Git-Friendly**: Easy to track with version control
- **Intuitive**: Enable/disable = drag & drop between folders

## 📦 Built-in portfolios (This directory)

**All `.json` files** in this directory are **automatically loaded** at startup.

### Official RegexLab portfolios

All portfolios in this directory are **integrity-protected** and readonly:

- **Status**: ✅ Always loaded (can't be disabled)
- **Readonly**: Yes (can't be edited via UI)
- **Protected**: Auto-restore from encrypted backup if corrupted
- **Multi-Portfolio Integrity**: Each portfolio has a unique encryption key

**Built-in portfolios:**
- All `.json` files in this directory are automatically protected
- Each portfolio verified on startup with integrity checks
- Auto-restored if corrupted or modified

**First built-in portfolio** (alphabetical order):
- Marked as "builtin principal" for backward compatibility
- Used as default active portfolio on first launch
- All portfolios verified on startup (STEP 0)

## 🔒 About the `readonly` flag

The `readonly` flag provides **soft protection** against accidental modifications via RegexLab commands.

### What `readonly` does

When `"readonly": true` is set in a portfolio:
- ✅ **Blocks modifications via RegexLab UI/commands**
  - Can't add patterns (`Portfolio.add_pattern()` raises `ValueError`)
  - Can't remove patterns (`Portfolio.remove_pattern()` raises `ValueError`)
  - Can't save portfolio (`PortfolioManager.save_portfolio()` raises `ValueError`)
- ✅ **Provides clear user feedback**
  - UI displays "(Built-in)" marker for readonly portfolios
  - Error messages explain why modification is blocked
- ✅ **Helps prevent accidents**
  - Users can't accidentally overwrite builtin patterns

### What `readonly` does NOT do

⚠️ **Important:** `readonly` is NOT a security feature!

- ❌ **Doesn't prevent direct file editing**
  - Users can manually edit the JSON file with any text editor
  - File system permissions are unchanged
- ❌ **Doesn't prevent file corruption**
  - Disk errors, incomplete writes, or manual edits can corrupt the file
  - Only the builtin portfolio (`regexlab-builtin.json`) has integrity protection
- ❌ **Doesn't encrypt or protect content**
  - Portfolio content is plain JSON, readable by anyone

### Multi-portfolio integrity protection (All builtins)

**All** builtin portfolios (in this directory) have **additional protection** via the integrity system:
- SHA256 signature verification on startup (each portfolio checked)
- Auto-restore from encrypted backup if corrupted
- **Unique encryption key per portfolio** (PBKDF2 with portfolio SHA256 as context)
- See `data/.regexlab/README.md` for technical details

**Summary:**
- `readonly` = Soft protection via RegexLab manager (UI/commands)
- Multi-Portfolio Integrity = Hard protection via cryptographic verification (all builtins)
- Each portfolio isolated: compromising one doesn't affect others

## ✏️ Creating your own portfolio

You can create custom portfolios for specific projects or use cases.

### Method 1: Use New Portfolio Wizard (Recommended)

The easiest way to create a portfolio:

1. Open Command Palette (`Ctrl+Shift+P`)
2. Run `Regex Lab: New Portfolio`
3. Follow the 5-step wizard:
   - Portfolio Name (validated)
   - Description (optional)
   - Author (optional, defaults to username)
   - Tags (optional)
   - Confirmation

The portfolio is automatically created in `User/RegexLab/portfolios/` and loaded immediately!

### Method 2: Create JSON File Manually

Create a new file in `User/RegexLab/portfolios/` (e.g., `my-portfolio.json`):

```json
{
    "name": "Portfolio Name",
    "description": "Description text",
    "version": "1.0.0",
    "author": "Author Name",
    "created": "2025-01-19",
    "updated": "2025-01-19",
    "tags": ["tag1", "tag2"],
    "readonly": false,
    "patterns": [
        {
            "name": "API Endpoint",
            "regex": "/api/v\\d+/[\\w/-]+",
            "type": "static",
            "description": "Match REST API endpoints"
        },
        {
            "name": "Custom Log",
            "regex": "\\[{{TIMESTAMP}}\\] {{LEVEL}}: {{MESSAGE}}",
            "type": "dynamic",
            "description": "Match custom log format with variables"
        }
    ]
}
```

**Done!** Restart Sublime Text or use **Portfolio Manager** (`Ctrl+K, Ctrl+P` → "Reload Portfolios") and your portfolio will be auto-loaded.

### Disabling a portfolio temporarily

Don't want to use a portfolio right now? Just move it:

```bash
# Disable (move to disabled folder)
User/RegexLab/portfolios/my-portfolio.json
    → User/RegexLab/disabled_portfolios/my-portfolio.json

# Re-enable (move back)
User/RegexLab/disabled_portfolios/my-portfolio.json
    → User/RegexLab/portfolios/my-portfolio.json
```

Or use **Portfolio Manager** (`Ctrl+K, Ctrl+P`) and select "Disable Portfolio".

## 🎯 Common use cases

### Minimal setup (Builtin only)

**Default behavior** - just install RegexLab:
- ✅ Built-in portfolios auto-loaded from `RegexLab/data/portfolios/`
- ✅ No custom portfolios
- ✅ Clean and minimal

### Developer setup (Add custom portfolios)

Create portfolios in `User/RegexLab/portfolios/`:
```
User/RegexLab/portfolios/
  ├── python-patterns.json    → Auto-loaded
  ├── django-patterns.json    → Auto-loaded
  └── web-patterns.json       → Auto-loaded
```

All portfolios in this folder are **automatically loaded** at startup!

### Project-specific workflow

**Working on Python project:**
```bash
# Move non-Python portfolios to disabled/
mv User/RegexLab/portfolios/web-patterns.json User/RegexLab/disabled_portfolios/
mv User/RegexLab/portfolios/django-patterns.json User/RegexLab/disabled_portfolios/
```

**Switching to Web project:**
```bash
# Move Python portfolios to disabled/
mv User/RegexLab/portfolios/python-patterns.json User/RegexLab/disabled_portfolios/

# Re-enable web portfolios
mv User/RegexLab/disabled_portfolios/web-patterns.json User/RegexLab/portfolios/
```

Or use **Portfolio Manager** (`Ctrl+K, Ctrl+P`) for visual enable/disable!

### Organizing portfolios by domain

Create domain-specific portfolios:
```
User/RegexLab/portfolios/
  ├── web-development.json     # URLs, emails, HTML
  ├── python-coding.json       # Python syntax, imports
  ├── log-analysis.json        # Various log formats
  └── data-formats.json        # CSV, JSON, XML
```

## 📋 Portfolio schema

### Required fields

Only `name` is strictly required. All other fields have default values:

```json
{
    "name": "Portfolio Name",           // Display name (REQUIRED, unique)
    "description": "Description text",  // Short description (optional, defaults to "")
    "version": "1.0.0",                 // Semantic version (optional, defaults to "1.0.0")
    "author": "Author Name",            // Creator name (optional, defaults to "")
    "created": "2025-01-19",            // Creation date YYYY-MM-DD (optional, auto-managed)
    "updated": "2025-01-19",            // Last update date YYYY-MM-DD (optional, auto-managed)
    "tags": ["tag1", "tag2"],           // Organization tags (optional, defaults to [])
    "readonly": false,                  // Can be edited via UI? (optional, defaults to false)
    "patterns": []                      // Pattern array (optional, defaults to [])
}
```

**Notes:**
- ✅ **Only `name` is required** - Portfolio creation will fail without it
- ✅ **All other fields are optional** - Missing fields use default values shown above
- ✅ **Auto-managed fields**: `created` and `updated` are automatically set/updated by RegexLab
- ℹ️ **Version**: Informational only, not enforced or used by RegexLab (useful for tracking your changes)
- 🏷️ **Tags**: Optional metadata for organization (future: may enable filtering/search)
- 🔒 **Readonly**: Defaults to `false` if omitted (editable via Portfolio Manager)

### Pattern types

#### Static pattern (No variables)

```json
{
    "name": "Email",
    "regex": "\\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\\.[A-Z|a-z]{2,}\\b",
    "type": "static",
    "description": "Match email addresses",
    "default_panel": "find"  // Optional: find, replace, find_in_files
}
```

#### Dynamic pattern (With variables)

```json
{
    "name": "Log Entry",
    "regex": "\\[{{DATE}}\\] {{LEVEL}}: {{MESSAGE}}",
    "type": "dynamic",
    "description": "Match log with custom fields"
}
```

**Variable format:**
- Use `{{VARIABLE_NAME}}` (double braces, case-insensitive)
- RegexLab will prompt for values when pattern is loaded
- Example: `{{DATE}}` → User enters `2025-01-19` → Final regex: `\[2025-01-19\]`

### Smart Panel Targeting (Optional)

Patterns can automatically open in the most appropriate Sublime Text panel using the **optional** `default_panel` field.

#### Why use `default_panel`?

**Without `default_panel`** (default behavior):
- Pattern always opens in the **Find panel** (`Ctrl+F`)
- User must manually switch to Replace or Find-in-Files if needed

**With `default_panel`** (optimized UX):
- Pattern opens in the **best panel for its purpose**
- Saves user time and clicks
- Clearer intent (e.g., "Email Finder" → auto-opens Find-in-Files)

#### Available panels

| Panel Value | Sublime Panel | Best For | Example Patterns |
|-------------|---------------|----------|------------------|
| `"find"` | Find (`Ctrl+F`) | **Default** - Validation, single-file search | Username validation, number formats |
| `"replace"` | Find & Replace (`Ctrl+H`) | Cleanup, transformation | Whitespace cleanup, duplicate removal, line ending fixes |
| `"find_in_files"` | Find in Files (`Ctrl+Shift+F`) | Multi-file search | Emails, URLs, IPs, phone numbers, file paths |

#### When to use each panel

**`"find_in_files"` — Multi-file search patterns:**
```json
{
    "name": "Email Finder",
    "regex": "[a-z0-9._%+-]+@[a-z0-9.-]+\\.[a-z]{2,}",
    "type": "static",
    "description": "Find all emails across your codebase",
    "default_panel": "find_in_files"
}
```
**Use for:** Network data (emails, URLs, IPs), file paths, cross-file references

**`"replace"` — Cleanup/transformation patterns:**
```json
{
    "name": "Trailing Whitespace Cleanup",
    "regex": "[ \\t]+$",
    "type": "static",
    "description": "Remove trailing spaces/tabs from lines",
    "default_panel": "replace"
}
```
**Use for:** Whitespace cleanup, duplicate removal, format normalization, line ending fixes

**`"find"` or omit — Validation/flexible patterns:**
```json
{
    "name": "Integer Validator",
    "regex": "^\\d+$",
    "type": "static",
    "description": "Match positive integers"
    // No default_panel = opens in Find (user decides context)
}
```
**Use for:** Validation patterns where context varies (validation, search, or replace)

#### Examples from built-in portfolios

**RXL - Data** portfolio uses smart panel targeting:

```json
{
    "patterns": [
        {
            "name": "Email (common)",
            "default_panel": "find_in_files"  // Multi-file email search
        },
        {
            "name": "URL (with protocol)",
            "default_panel": "find_in_files"  // Find URLs across project
        },
        {
            "name": "IPv4 address",
            "default_panel": "find_in_files"  // Locate IPs in configs
        },
        {
            "name": "Multiple spaces (2+)",
            "default_panel": "replace"  // Cleanup extra spacing
        },
        {
            "name": "Trailing whitespace",
            "default_panel": "replace"  // Remove line-end spaces
        },
        {
            "name": "Integer (positive)",
            // No default_panel = Find (validation context varies)
        }
    ]
}
```

#### Best practices

✅ **DO use `default_panel` for:**
- Clear single-purpose patterns (email finder = find_in_files)
- Cleanup patterns that always need Replace panel
- Network/data patterns meant for cross-file search

❌ **DON'T use `default_panel` for:**
- Validation patterns (context varies)
- Multi-purpose patterns (user decides find vs replace)
- Patterns where intent is ambiguous

⚠️ **Tip:** Use the **Portfolio Wizard** (`RegexLab: New Portfolio`) or **Portfolio Manager** (`Ctrl+K, Ctrl+P`) to create/edit patterns ; they help you choose the right `default_panel` automatically! Manual JSON editing is error-prone and easy to mess up.

### Optional fields

- `default_panel`: Which panel to open (`"find"`, `"replace"`, `"find_in_files"`)
- Any custom metadata you want to track

## 🔍 Multi-portfolio verification on startup

When RegexLab loads, it verifies **all builtin portfolios** before loading any portfolio:

**Example console output:**
```
[RegexLab] STEP 0 - Multi-Portfolio Integrity Verification
[RegexLab] Verifying multi-portfolio integrity...
[RegexLab] ✓ All 3 builtin portfolios verified
[RegexLab] ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
[RegexLab:DEBUG] Configured portfolios to load: 4
[RegexLab:DEBUG] Loading portfolio 1/4: RegexLab/data/portfolios/builtin-example.json
[RegexLab] ✓ Portfolio loaded: Example Portfolio (Built-in)
[RegexLab]   Patterns: 12
[RegexLab:DEBUG] Loading portfolio 2/4: User/RegexLab/portfolios/my-custom.json
[RegexLab] ✓ Portfolio loaded: My Custom Portfolio
[RegexLab]   Patterns: 7
[RegexLab] ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
[RegexLab] RegexLab initialized: 4 portfolio(s) loaded
```

> **Note:** This is an example. Actual portfolio names and counts depend on your installation.

**STEP 0** verifies integrity before loading:
- Each builtin portfolio checked independently
- If corruption detected → Auto-restore from encrypted backup
- Example restoration log:
  ```
  [RegexLab] ⚠ Restored 1 portfolios:
  [RegexLab]   - web-development.json - RESTORED (corrupted)
  ```

## 🐛 Troubleshooting

### Portfolio not showing up

**Check:**
1. Is the file in `User/RegexLab/portfolios/`? (NOT `disabled_portfolios/`)
2. Does the filename end with `.json`?
3. Is the JSON valid? (no syntax errors)
4. Did you restart Sublime Text or reload portfolios?

**View console:**
- `View > Show Console` to see loading errors
- **Enable DEBUG logging** for detailed info:
  - `Preferences > Package Settings > RegexLab > Settings`
  - Set `"log_level": "DEBUG"`
  - Restart Sublime Text or reload portfolios
  - Check console for detailed loading steps

### "Invalid portfolio" error

```
[RegexLab] ✗ Invalid portfolio: ... - Missing required field: 'name'
```

**Solution:**
- Make sure the `name` field is present (only required field)
- Validate JSON syntax (commas, quotes, brackets)
- Check pattern structure matches schema (see above)

### Portfolio loads but patterns don't appear

**Possible causes:**
1. Portfolio has `"patterns": []` (empty array)
2. Pattern regex is invalid (check console for errors)
3. Portfolio name conflicts with another portfolio (duplicate names)

**Solution:**
- Open portfolio file and verify patterns array
- Check pattern syntax (see Portfolio schema below)
- Use unique portfolio names

## 📝 Tips

### Built-in portfolios are always first

**All** built-in portfolios (from `RegexLab/data/portfolios/`) are:
- ✅ Verified first (STEP 0 - multi-portfolio integrity check)
- ✅ Loaded before custom portfolios (alphabetical order)
- ✅ Integrity-protected (auto-restore if corrupted or missing)
- ✅ Each portfolio isolated (unique encryption key per portfolio)
- ✅ Show "(Built-in)" tag in Quick Panel
- ✅ Separated at top of pattern list
- ⚠️ Can't be disabled (always loaded)

**First built-in** (alphabetical):
- Marked as "builtin principal" for backward compatibility
- Used as default active portfolio on first launch
- All portfolios loaded equally, first one just has special flag

### Performance

- Each portfolio adds ~0.01s to startup time
- Keep active portfolios under 10 for best performance
- Move unused portfolios to `disabled_portfolios/` instead of deleting

### Managing many portfolios

**Use Portfolio Manager** (`Ctrl+K, Ctrl+P`):
- See all loaded portfolios at a glance
- View disabled portfolios (if any exist)
- Enable/disable with one click
- Create new portfolios via wizard

### Version control (Git)

Add to `.gitignore`:
```gitignore
# Don't track disabled portfolios
User/RegexLab/disabled_portfolios/

# Do track active portfolios
!User/RegexLab/portfolios/*.json
```

This way your team shares active portfolios, but disabled ones stay local.

## 🔗 Related documentation

- **Integrity System**: See `data/.regexlab/README.md` for builtin portfolio protection
- **Portfolio Manager**: Press `Ctrl+K, Ctrl+P` to manage portfolios visually
- **New Portfolio Wizard**: `Ctrl+Shift+P` → "RegexLab: New Portfolio"
- **Settings**: Full settings documentation in default settings file
- **Commands**: List available via Command Palette (`Ctrl+Shift+P` → "RegexLab")

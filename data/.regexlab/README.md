# 🛡️ RegexLab Integrity System (Multi-Portfolio v2)

Hey! This directory contains integrity protection files for **all builtin RegexLab portfolios**.

## ⚠️ What's this for?

**Heads up:** This is NOT cryptographic security against attacks.

The integrity system protects all builtin portfolios against:
- ✅ Accidental modifications by users
- ✅ File corruption (disk errors, partial writes)
- ✅ Unintended edits that break patterns
- ✅ Plugin malfunction due to corrupted data

**Goal:** Make sure all builtin portfolios work reliably for everyone. If corruption is detected on any portfolio, the plugin auto-restores from the encrypted backup.

## 📁 Files

### `salt.key` (32 bytes)

Master cryptographic random salt used for all portfolio key derivations.

- **DO NOT MODIFY** this file or the entire integrity system will fail for ALL portfolios
- **DO NOT DELETE** or restoration won't work for ANY portfolio
- Generated once by developers, distributed with the plugin

### `rxl.kst` (Multi-Portfolio Keystore)

Encrypted backup of **ALL builtin portfolios** with integrity signatures.

**Format:**
```
[Header]       2-digit count (e.g., "03" = 3 portfolios, max 99)
[Block 1]      SHA256(64) + Size(5) + Encrypted_Data(variable)
[Block 2]      SHA256(64) + Size(5) + Encrypted_Data(variable)
[Block 3]      SHA256(64) + Size(5) + Encrypted_Data(variable)
...
```

**Each block:**
- `SHA256` (64 bytes hex): Portfolio fingerprint (used for key derivation context)
- `Size` (5 bytes): Encrypted data size (e.g., "01234" = 1234 bytes)
- `Encrypted_Data`: XOR-encrypted portfolio JSON

**Security:**
- Each portfolio gets a **unique encryption key** (PBKDF2 with portfolio SHA256 as context)
- Compromising one portfolio's encryption does NOT affect others
- Self-contained: keys derived from salt + portfolio content hash

- **DO NOT MODIFY** this file or restoration will fail
- Contains encrypted copies of **ALL** `data/portfolios/*.json` builtin portfolios

## 🔧 How it works

### Key Derivation (Per-Portfolio Isolation)

```python
# Each portfolio gets a UNIQUE key:
password = salt + SHA256(portfolio_content)  # Unique context per portfolio
key = PBKDF2_HMAC(
    algorithm='sha256',
    password=password,
    salt=salt,               # Master salt from salt.key
    iterations=100000,       # Computationally expensive
    dklen=32                 # 256-bit key
)
```

**Why unique keys per portfolio?**
- Compromising one portfolio's encryption does NOT affect others
- Each portfolio isolated: different content → different SHA256 → different key
- Portfolio content serves as cryptographic context

### Integrity Verification (On Plugin Startup)

```
For EACH builtin portfolio (*.json in data/portfolios/):
1. Read current portfolio file
2. Compute SHA256(portfolio_content)
3. Find matching block in rxl.kst (compare SHA256)
4. If block found and SHA256 matches:
   → Portfolio OK, skip
5. If mismatch or missing:
   → Corruption detected!
   → Derive unique key (PBKDF2 + portfolio SHA256)
   → Decrypt block from rxl.kst
   → Restore portfolio file
   → Log restoration event
6. If restore fails → Show error (user must reinstall)
```

### Auto-Restore

If **any** builtin portfolio is corrupted (modified, incomplete, malformed), RegexLab automatically restores it from the encrypted backup in `rxl.kst`.

**Restoration scope:**
- Each portfolio verified and restored independently
- Corruption in one portfolio doesn't affect others
- All portfolios checked on every plugin startup (STEP 0)

**Restoration limitations:**
- If **both** `rxl.kst` and `salt.key` are corrupted → Can't restore any portfolio (user must reinstall)
- If `rxl.kst` is corrupted (invalid format, truncated) → Can't restore any portfolio (user must reinstall)
- If `salt.key` is modified → All keys change → Decryption fails for all portfolios (user must reinstall)
- If a portfolio is missing from `rxl.kst` → Can't restore that specific portfolio (regenerate keystore)

## 🛡️ Security Model

**This is simple protection, NOT military-grade encryption:**
- Key Derivation: PBKDF2-HMAC-SHA256 (100,000 iterations) with per-portfolio context
- Encryption: XOR with derived key (Python stdlib only, no external dependencies)
- Good enough for detecting tampering and preventing casual modifications
- **Not** designed to resist determined attackers
- **Not** designed to protect secrets (there are none)

**Per-Portfolio Isolation:**
- Each portfolio gets its own **unique key**
- Key depends on: `salt.key` + portfolio content hash (SHA256)
- Compromising one portfolio doesn't give access to others
- Portfolio interdependence: changing one portfolio changes its key (not others)

**Mutual Protection:**
- `salt.key` protects all passwords (modify it = all portfolios break)
- `rxl.kst` signatures protect all portfolios (modify any portfolio = detected)
- Both files protect the entire system's integrity

## 🔄 Regeneration

**For developers only:** If you update any builtin portfolio patterns, regenerate the integrity files:

```bash
sublime.run_command("regexlab_generate_integrity")  # ST console
```

This will regenerate **both** `salt.key` and `rxl.kst`:

1. Scan **all** `data/portfolios/*.json` files (auto-discovery)
2. Generate new `salt.key` (32 random bytes)
3. **For each portfolio:**
   - Compute SHA256(portfolio_content)
   - Derive unique key (PBKDF2 + portfolio SHA256 context)
   - Encrypt portfolio with unique key
   - Create block: SHA256(64) + Size(5) + Encrypted_Data
4. Assemble `rxl.kst`:
   - Header: portfolio count (e.g., "03")
   - Concatenate all blocks
5. Verify the keystore works (test decryption)

**⚠️ Warning:** Regenerating creates completely new `salt.key` and `rxl.kst` files! Make sure to commit the new files to version control.

**When to regenerate:**
- Adding a new builtin portfolio
- Modifying any builtin portfolio patterns
- Removing a builtin portfolio
- After any change to `data/portfolios/*.json`

## 🐛 Troubleshooting

### Error: "Builtin portfolio [name] is CORRUPTED and cannot be recovered!"

**Causes:**
- Both `salt.key` and `rxl.kst` are missing or corrupted
- Someone modified `salt.key` (ALL keys no longer match)
- `rxl.kst` format is invalid
- Portfolio missing from `rxl.kst` (not in keystore)

**Solution:**
1. Uninstall RegexLab via Package Control
2. Reinstall RegexLab
3. Fresh integrity files will be included (all portfolios protected)

### Warning: "⚠ [portfolio.json] - RESTORED (corrupted)" or "RESTORED (missing)"

**Causes:**
- Someone manually edited a builtin portfolio file
- File corruption (disk error, incomplete write)
- File accidentally deleted

**Solution:**
- Plugin automatically restores from `rxl.kst`
- No action needed if restoration succeeds
- Check logs: "✓ All X builtin portfolios verified" (OK) or "⚠ Restored Y portfolios" (auto-fixed)
- If restoration fails for any portfolio, reinstall the plugin

### Info: "✓ All X builtin portfolios verified"

This is **good news**! All builtin portfolios passed integrity checks.

- `X` = number of builtin portfolios found in `data/portfolios/`
- Example: "✓ All 3 builtin portfolios verified"
- Appears on every plugin startup (STEP 0)

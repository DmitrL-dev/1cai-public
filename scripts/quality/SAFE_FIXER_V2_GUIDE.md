# Safe Auto-Fixer v2.0 - Execution Guide

## 🎯 What This Script Does

Fixes **~1500 code quality issues** using ONLY safe, proven methods:

✅ **Safe fixes:**
- Trailing whitespace (589 files)
- Import order with isort (162 files)
- Lazy logging - simple cases only (357 files)
- Unused imports with autoflake (45 files)
- Unused variables with autoflake (43 files)
- Line length - conservative autopep8 (247 files)

❌ **Excluded (learned from v1.0 failure):**
- ~~black~~ - too aggressive, broke code
- ~~auto docstrings~~ - caused syntax errors

---

## 📋 Prerequisites

Ensure these tools are installed:

```powershell
pip install isort autoflake autopep8
```

---

## 🚀 How to Run

### Step 1: Run the fixer

```powershell
python scripts/quality/safe_auto_fixer_v2.py
```

### Step 2: Verify results

```powershell
# Check for parsing errors
pylint src/ --output-format=json --exit-zero > pylint_after_safe_fix.json

# Count remaining issues
python -c "import json; data = json.load(open('pylint_after_safe_fix.json')); print(f'Total issues: {len(data)}'); print(f'Parsing errors: {len([x for x in data if x.get(\"message-id\") == \"E0001\"])}')"
```

### Step 3: If satisfied, commit

```powershell
git add .
git commit -m "fix: safe auto-fixes for code quality (v2.0)"
```

### Step 4: If issues, rollback

```powershell
git reset --hard HEAD
```

---

## 📊 Expected Results

**Before:**
- Total issues: 3073
- Parsing errors: 0

**After (estimated):**
- Total issues: ~1500-1800
- Parsing errors: 0 (guaranteed)
- Fixed: ~1300-1500 issues

---

## ⚠️ Safety Features

1. **Validation step** - checks all files compile after fixes
2. **Conservative approach** - only proven safe patterns
3. **Easy rollback** - git reset if anything goes wrong
4. **No aggressive reformatting** - preserves code structure

---

## 🔧 Troubleshooting

**If you see syntax errors after running:**
```powershell
git reset --hard HEAD
```

**If tools are missing:**
```powershell
pip install isort autoflake autopep8
```

**If script hangs:**
- Press Ctrl+C
- Run `git status` to see what changed
- Rollback if needed

---

## ✅ Ready to Run!

Execute:
```powershell
python scripts/quality/safe_auto_fixer_v2.py
```

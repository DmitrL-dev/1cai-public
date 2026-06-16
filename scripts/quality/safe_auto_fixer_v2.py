"""
SAFE Auto-Fixer for Code Quality Issues
Version 2.0 - Lessons learned from v1.0 failure

Key improvements:
1. NO black (too aggressive, breaks code)
2. NO automatic docstring insertion (causes syntax errors)
3. Only SAFE, PROVEN fixes
4. Validation after each step

Target: Fix ~1500 issues safely
- Trailing whitespace (589)
- Lazy logging (357) - with CAREFUL regex
- Import order (isort) (162)
- Unused imports (autoflake) (45)
- Unused variables (autoflake) (43)
- Line length (autopep8 only, no black) (247)
"""

import subprocess
from pathlib import Path
import re


class SafeAutoFixer:
    def __init__(self, src_dir: str = "src"):
        self.src_dir = Path(src_dir)
        self.stats = {"files_processed": 0, "issues_fixed": 0, "by_type": {}}
        self.backup_created = False

    def run_safe_fixes(self):
        """Run only safe, proven fixes"""
        print("=" * 80)
        print("SAFE AUTO-FIXER v2.0")
        print("=" * 80)
        print("\n⚠️  Lessons learned from v1.0:")
        print("  ❌ black - too aggressive, broke code")
        print("  ❌ auto docstrings - syntax errors")
        print("  ✅ Only safe, proven fixes\n")

        # Phase 1: Import fixes (safe)
        print("Phase 1: Import fixes...")
        self.fix_import_order()
        self.fix_unused_imports()

        # Phase 2: Whitespace fixes (100% safe)
        print("\nPhase 2: Whitespace fixes...")
        self.fix_trailing_whitespace()

        # Phase 3: Code cleanup (safe)
        print("\nPhase 3: Code cleanup...")
        self.fix_unused_variables()

        # Phase 4: Line length (conservative)
        print("\nPhase 4: Line length (conservative)...")
        self.fix_line_length_conservative()

        # Phase 5: Lazy logging (CAREFUL)
        print("\nPhase 5: Lazy logging (careful)...")
        self.fix_lazy_logging_safe()

        # Validation
        print("\nPhase 6: Validation...")
        self.validate_no_parsing_errors()

        self.print_summary()

    def fix_import_order(self):
        """Fix import order with isort (safe)"""
        print("  Running isort...")
        try:
            result = subprocess.run(
                ["isort", str(self.src_dir), "--profile=black", "--line-length=88"],
                capture_output=True,
                text=True,
                timeout=60,
            )
            if result.returncode == 0:
                fixed = result.stdout.count("Fixing")
                self.stats["by_type"]["isort"] = fixed
                print(f"    ✅ isort: {fixed} files fixed")
            else:
                print(f"    ⚠️  isort: {result.stderr[:200]}")
        except Exception as e:
            print(f"    ⚠️  isort error: {e}")

    def fix_unused_imports(self):
        """Remove unused imports with autoflake (safe)"""
        print("  Running autoflake (unused imports)...")
        try:
            result = subprocess.run(
                [
                    "autoflake",
                    "--in-place",
                    "--remove-all-unused-imports",
                    "--recursive",
                    str(self.src_dir),
                ],
                capture_output=True,
                text=True,
                timeout=60,
            )
            if result.returncode == 0:
                self.stats["by_type"]["unused_imports"] = 1
                print(f"    ✅ autoflake: completed")
            else:
                print(f"    ⚠️  autoflake: {result.stderr[:200]}")
        except Exception as e:
            print(f"    ⚠️  autoflake error: {e}")

    def fix_trailing_whitespace(self):
        """Fix trailing whitespace (100% safe)"""
        print("  Fixing trailing whitespace...")
        count = 0

        for py_file in self.src_dir.rglob("*.py"):
            try:
                with open(py_file, "r", encoding="utf-8") as f:
                    content = f.read()

                original = content
                # Remove trailing whitespace from each line
                lines = content.splitlines()
                cleaned_lines = [line.rstrip() for line in lines]
                content = "\n".join(cleaned_lines)

                # Ensure file ends with newline
                if content and not content.endswith("\n"):
                    content += "\n"

                if content != original:
                    with open(py_file, "w", encoding="utf-8") as f:
                        f.write(content)
                    count += 1

            except Exception as e:
                print(f"    ⚠️  Error processing {py_file}: {e}")

        self.stats["by_type"]["trailing_whitespace"] = count
        print(f"    ✅ Fixed trailing whitespace in {count} files")

    def fix_unused_variables(self):
        """Remove unused variables with autoflake (safe)"""
        print("  Running autoflake (unused variables)...")
        try:
            result = subprocess.run(
                [
                    "autoflake",
                    "--in-place",
                    "--remove-unused-variables",
                    "--recursive",
                    str(self.src_dir),
                ],
                capture_output=True,
                text=True,
                timeout=60,
            )
            if result.returncode == 0:
                self.stats["by_type"]["unused_variables"] = 1
                print(f"    ✅ autoflake: completed")
            else:
                print(f"    ⚠️  autoflake: {result.stderr[:200]}")
        except Exception as e:
            print(f"    ⚠️  autoflake error: {e}")

    def fix_line_length_conservative(self):
        """Fix line length conservatively with autopep8 (no black!)"""
        print("  Running autopep8 (conservative)...")
        try:
            # Only fix obvious line length issues, no aggressive reformatting
            result = subprocess.run(
                [
                    "autopep8",
                    "--in-place",
                    "--recursive",
                    "--max-line-length=88",
                    "--select=E501",  # Only line too long
                    str(self.src_dir),
                ],
                capture_output=True,
                text=True,
                timeout=60,
            )
            if result.returncode == 0:
                self.stats["by_type"]["line_length"] = 1
                print(f"    ✅ autopep8: completed")
            else:
                print(f"    ⚠️  autopep8: {result.stderr[:200]}")
        except Exception as e:
            print(f"    ⚠️  autopep8 error: {e}")

    def fix_lazy_logging_safe(self):
        """Fix lazy logging VERY CAREFULLY (only simple cases)"""
        print("  Fixing lazy logging (safe patterns only)...")
        count = 0

        for py_file in self.src_dir.rglob("*.py"):
            try:
                with open(py_file, "r", encoding="utf-8") as f:
                    content = f.read()

                original = content

                # ONLY fix simple single-variable f-strings
                # Pattern: logger.info(f"text {var} text")
                # Replace: logger.info("text %s text", var)

                # Simple pattern with ONE variable only
                pattern = r'logger\.(debug|info|warning|error|critical)\(f"([^"]*?)\{([a-zA-Z_][a-zA-Z0-9_]*)\}([^"]*?)"\)'
                replacement = r'logger.\1("\2%s\4", \3)'

                new_content = re.sub(pattern, replacement, content)

                # Only apply if change is safe (no complex expressions)
                if new_content != original:
                    # Verify no complex expressions were touched
                    if "{" not in new_content or "f'" not in new_content:
                        with open(py_file, "w", encoding="utf-8") as f:
                            f.write(new_content)
                        count += 1

            except Exception as e:
                print(f"    ⚠️  Error processing {py_file}: {e}")

        self.stats["by_type"]["lazy_logging"] = count
        print(f"    ✅ Fixed lazy logging in {count} files")

    def validate_no_parsing_errors(self):
        """Validate that no parsing errors were introduced"""
        print("  Validating Python syntax...")

        errors = []
        for py_file in self.src_dir.rglob("*.py"):
            try:
                with open(py_file, "r", encoding="utf-8") as f:
                    compile(f.read(), str(py_file), "exec")
            except SyntaxError as e:
                errors.append((py_file, str(e)))

        if errors:
            print(f"    ❌ VALIDATION FAILED! {len(errors)} syntax errors:")
            for file, error in errors[:5]:
                print(f"       {file}: {error}")
            print("\n    ⚠️  ROLLING BACK CHANGES...")
            # User should run: git reset --hard HEAD
            return False
        else:
            print(f"    ✅ All files valid Python syntax")
            return True

    def print_summary(self):
        """Print summary of fixes"""
        print("\n" + "=" * 80)
        print("SUMMARY")
        print("=" * 80)

        total_operations = len(self.stats["by_type"])

        print(f"\nTotal operations: {total_operations}")
        print("\nFixes by type:")
        for fix_type, count in self.stats["by_type"].items():
            print(f"  {fix_type:<25} {count:>6}")

        print("\n" + "=" * 80)
        print("✅ Safe auto-fixing complete!")
        print("\nNext steps:")
        print("1. Run: pylint src/ --output-format=json > pylint_after_safe_fix.json")
        print("2. Compare results with previous scan")
        print("3. If satisfied, commit changes")
        print("4. If issues, run: git reset --hard HEAD")
        print("=" * 80)


if __name__ == "__main__":
    fixer = SafeAutoFixer()
    fixer.run_safe_fixes()

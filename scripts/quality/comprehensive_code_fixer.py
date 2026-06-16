#!/usr/bin/env python3
"""
Comprehensive Code Quality Fixer
Fixes all pylint issues automatically where possible.
"""

import re
import subprocess
from pathlib import Path

SRC_DIR = Path("c:/1cAI/src")

stats = {
    "files_processed": 0,
    "whitespace_fixed": 0,
    "imports_removed": 0,
    "variables_fixed": 0,
    "logging_fixed": 0,
}


def run_autopep8():
    """Run autopep8 to fix PEP 8 issues."""
    print("🔧 Running autopep8...")
    cmd = [
        "autopep8",
        "--in-place",
        "--recursive",
        "--aggressive",
        "--aggressive",
        str(SRC_DIR),
    ]
    try:
        subprocess.run(cmd, check=True, capture_output=True)
        print("✅ autopep8 complete")
        return True
    except subprocess.CalledProcessError as e:
        print(f"⚠️ autopep8 failed: {e}")
        return False
    except FileNotFoundError:
        print("⚠️ autopep8 not installed, skipping")
        return False


def run_autoflake():
    """Run autoflake to remove unused imports and variables."""
    print("🔧 Running autoflake...")
    cmd = [
        "autoflake",
        "--in-place",
        "--recursive",
        "--remove-all-unused-imports",
        "--remove-unused-variables",
        str(SRC_DIR),
    ]
    try:
        result = subprocess.run(cmd, check=True, capture_output=True, text=True)
        print("✅ autoflake complete")
        # Count fixes from output
        if result.stdout:
            stats["imports_removed"] = result.stdout.count("removed")
        return True
    except subprocess.CalledProcessError as e:
        print(f"⚠️ autoflake failed: {e}")
        return False
    except FileNotFoundError:
        print("⚠️ autoflake not installed, skipping")
        return False


def run_isort():
    """Run isort to organize imports."""
    print("🔧 Running isort...")
    cmd = ["isort", str(SRC_DIR)]
    try:
        subprocess.run(cmd, check=True, capture_output=True)
        print("✅ isort complete")
        return True
    except subprocess.CalledProcessError as e:
        print(f"⚠️ isort failed: {e}")
        return False
    except FileNotFoundError:
        print("⚠️ isort not installed, skipping")
        return False


def run_black():
    """Run black to format code."""
    print("🔧 Running black...")
    cmd = ["black", str(SRC_DIR), "--line-length", "88"]
    try:
        subprocess.run(cmd, check=True, capture_output=True)
        print("✅ black complete")
        return True
    except subprocess.CalledProcessError as e:
        print(f"⚠️ black failed: {e}")
        return False
    except FileNotFoundError:
        print("⚠️ black not installed, skipping")
        return False


def fix_lazy_logging(content: str) -> tuple[str, int]:
    """Fix lazy logging format strings."""
    count = 0
    lines = content.split('\n')
    new_lines = []
    
    for line in lines:
        # Match: logger.info(f"...")
        if re.search(r'logger\.(debug|info|warning|error|critical)\(f["\']', line):
            # Replace f-string with % formatting
            line = re.sub(
                r'logger\.(\w+)\(f["\'](.+?)["\']',
                r'logger.\1("\2"',
                line
            )
            # Replace {var} with %s
            line = re.sub(r'\{(\w+)\}', r'%s', line)
            count += 1
        new_lines.append(line)
    
    return '\n'.join(new_lines), count


def fix_unused_arguments(content: str) -> tuple[str, int]:
    """Prefix unused arguments with underscore."""
    count = 0
    # This is complex and requires AST analysis
    # For now, skip - will be handled manually
    return content, count


def process_file_custom_fixes(filepath: Path) -> bool:
    """Apply custom fixes to a file."""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        
        original_content = content
        
        # Fix lazy logging
        content, logging_count = fix_lazy_logging(content)
        stats["logging_fixed"] += logging_count
        
        # Write back if changed
        if content != original_content:
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(content)
            stats["files_processed"] += 1
            return True
        
        return False
    except Exception as e:
        print(f"Error processing {filepath}: {e}")
        return False


def install_tools():
    """Install required tools if not present."""
    print("📦 Checking required tools...")
    tools = ["autopep8", "autoflake", "isort", "black"]
    
    for tool in tools:
        try:
            subprocess.run([tool, "--version"], capture_output=True, check=True)
            print(f"✅ {tool} installed")
        except (subprocess.CalledProcessError, FileNotFoundError):
            print(f"⚠️ {tool} not found, installing...")
            try:
                subprocess.run(
                    ["pip", "install", tool],
                    check=True,
                    capture_output=True
                )
                print(f"✅ {tool} installed")
            except subprocess.CalledProcessError as e:
                print(f"❌ Failed to install {tool}: {e}")


def main():
    """Main entry point."""
    print("=" * 70)
    print("🔧 COMPREHENSIVE CODE QUALITY FIXER")
    print("=" * 70)
    print()
    
    # Install tools
    install_tools()
    print()
    
    # Phase 1: Auto-formatters
    print("📋 Phase 1: Running Auto-Formatters")
    print("-" * 70)
    run_autopep8()
    run_autoflake()
    run_isort()
    run_black()
    print()
    
    # Phase 2: Custom fixes
    print("📋 Phase 2: Applying Custom Fixes")
    print("-" * 70)
    python_files = list(SRC_DIR.rglob("*.py"))
    for filepath in python_files:
        process_file_custom_fixes(filepath)
    print()
    
    # Statistics
    print("=" * 70)
    print("📊 STATISTICS")
    print("=" * 70)
    print(f"Files processed:     {stats['files_processed']}")
    print(f"Imports removed:     {stats['imports_removed']}")
    print(f"Logging fixed:       {stats['logging_fixed']}")
    print("=" * 70)
    print()
    print("✅ Automated fixes complete!")
    print("🔍 Run 'pylint src/' to verify improvements")
    print()
    print("⚠️ Note: Some issues require manual fixes:")
    print("  - Parsing errors (indentation)")
    print("  - Missing docstrings")
    print("  - Complex refactoring")


if __name__ == "__main__":
    main()

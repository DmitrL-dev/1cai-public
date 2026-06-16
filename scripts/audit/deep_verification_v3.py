#!/usr/bin/env python3
"""
DEEP VERIFICATION V3 - ULTIMATE PROJECT AUDIT
Strictly follows "CRITICAL RULES OF VERIFICATION" (Nov 7, 2025)
"""

import os
import re
import sys
import time
import urllib.error
import urllib.request
from collections import defaultdict
from pathlib import Path

# Configuration
IGNORE_DIRS = {
    '.git', '__pycache__', 'node_modules', 'venv', '.venv', 'env', '.env', 
    '.pytest_cache', '.mypy_cache', 'dist', 'build', 'coverage', 'htmlcov',
    'temp_repos'
}
IGNORE_EXTENSIONS = {
    '.pyc', '.pyo', '.pyd', '.so', '.dll', '.dylib', '.exe', '.bin', 
    '.png', '.jpg', '.jpeg', '.gif', '.ico', '.svg', '.woff', '.woff2', 
    '.ttf', '.eot', '.mp4', '.webm', '.mp3', '.wav', '.zip', '.tar', 
    '.gz', '.7z', '.rar', '.pdf', '.doc', '.docx', '.xls', '.xlsx', 
    '.ppt', '.pptx', '.odt', '.ods', '.odp'
}

class DeepVerifier:
    def __init__(self):
        self.root = Path('.').resolve()
        self.issues = []
        self.stats = defaultdict(int)
        self.files_checked = 0
        self.start_time = time.time()

    def log_issue(self, level, category, message, file=None, line=None):
        issue = {
            'level': level, # 'CRITICAL', 'WARNING', 'INFO'
            'category': category,
            'message': message,
            'file': str(file) if file else None,
            'line': line
        }
        self.issues.append(issue)
        print(f"[{level}] {category}: {message}" + (f" ({file}:{line})" if file else ""))

    def is_ignored(self, path):
        parts = path.parts
        for part in parts:
            if part in IGNORE_DIRS:
                return True
        if path.suffix in IGNORE_EXTENSIONS:
            return True
        return False

    def walk_files(self):
        for root, dirs, files in os.walk(self.root):
            # Modify dirs in-place to skip ignored directories
            dirs[:] = [d for d in dirs if d not in IGNORE_DIRS]
            
            for file in files:
                path = Path(root) / file
                if not self.is_ignored(path):
                    yield path

    def check_1_hidden_folders(self):
        """Check for hidden folders (.folder) that might contain sensitive data."""
        print("\n[1/10] Checking for hidden folders...")
        for root, dirs, files in os.walk(self.root):
            for d in dirs:
                if d.startswith('.') and d not in IGNORE_DIRS and d != '.github' and d != '.vscode' and d != '.devcontainer':
                    # Check if it contains suspicious files
                    dir_path = Path(root) / d
                    has_files = any(dir_path.iterdir())
                    if has_files:
                        self.log_issue('WARNING', 'HIDDEN_FOLDER', f"Found hidden folder with content: {d}", dir_path)

    def check_2_private_paths(self):
        """Check for hardcoded private paths (C:\\Users, /home/user, etc.)."""
        print("\n[2/10] Checking for private paths...")
        patterns = [
            r'C:\\Users\\',
            r'/home/[a-zA-Z0-9]+/',
            r'/Users/[a-zA-Z0-9]+/',
            r'Desktop\\',
            r'Downloads\\'
        ]
        
        for path in self.walk_files():
            try:
                content = path.read_text(errors='ignore')
                for pattern in patterns:
                    if re.search(pattern, content, re.IGNORECASE):
                        # Exclude this script itself
                        if path.name == 'deep_verification_v3.py':
                            continue
                        self.log_issue('CRITICAL', 'PRIVATE_PATH', f"Found private path pattern '{pattern}'", path)
            except Exception as e:
                pass

    def check_3_security_patterns(self):
        """Check for secrets, CORS, SQLi."""
        print("\n[3/10] Checking security patterns...")
        
        secret_patterns = [
            (r'sk-[a-zA-Z0-9]{20,}', 'OpenAI Key'),
            (r'ghp_[a-zA-Z0-9]{20,}', 'GitHub Token'),
            (r'xoxb-[a-zA-Z0-9]{10,}', 'Slack Token'),
            (r'-----BEGIN RSA PRIVATE KEY-----', 'RSA Private Key'),
            (r'allow_origins=\["\*"\]', 'Insecure CORS'),
            (r'allow_origins=\[\'\*\'\]', 'Insecure CORS'),
        ]

        for path in self.walk_files():
            try:
                content = path.read_text(errors='ignore')
                
                # Secrets & CORS
                for pattern, name in secret_patterns:
                    if re.search(pattern, content):
                        if path.name == 'deep_verification_v3.py': continue
                        self.log_issue('CRITICAL', 'SECURITY', f"Found {name}", path)

                # SQL Injection (rough check for f-strings in execute)
                if path.suffix == '.py':
                    if re.search(r'\.execute\(f[\'"]', content) or re.search(r'\.execute\(".*\{.+\}.*"', content):
                        self.log_issue('CRITICAL', 'SQL_INJECTION', "Potential SQL injection (f-string in execute)", path)

            except Exception:
                pass

    def check_4_rate_limiting(self):
        """Check if API endpoints have rate limiting."""
        print("\n[4/10] Checking rate limiting...")
        # Look for FastAPI/Flask routes
        for path in self.walk_files():
            if path.suffix == '.py':
                try:
                    content = path.read_text(errors='ignore')
                    if '@app.post' in content or '@app.get' in content or '@router.post' in content:
                        # It's likely an API file
                        if '/generate' in content or '/create' in content or '/upload' in content:
                            if '@limiter' not in content and 'RateLimiter' not in content:
                                self.log_issue('CRITICAL', 'RATE_LIMITING', "API endpoint without rate limiting", path)
                except Exception:
                    pass

    def check_5_timeouts(self):
        """Check for missing timeouts in requests/aiohttp calls."""
        print("\n[5/10] Checking timeouts...")
        for path in self.walk_files():
            if path.suffix == '.py':
                try:
                    content = path.read_text(errors='ignore')
                    # Check requests.get/post without timeout
                    if re.search(r'requests\.(get|post|put|delete|patch)\(', content):
                        if 'timeout=' not in content:
                            self.log_issue('CRITICAL', 'TIMEOUT', "External API call without timeout", path)
                    
                    # Check aiohttp
                    if 'aiohttp.ClientSession' in content and 'timeout=' not in content:
                         self.log_issue('WARNING', 'TIMEOUT', "aiohttp session might be missing timeout", path)
                except Exception:
                    pass

    def check_6_pydantic_validation(self):
        """Check Pydantic models for string constraints."""
        print("\n[6/10] Checking Pydantic validation...")
        for path in self.walk_files():
            if path.suffix == '.py':
                try:
                    content = path.read_text(errors='ignore')
                    if 'BaseModel' in content:
                        # Very basic check: if str is used as type hint but no Field(..., max_length=...)
                        # This is hard to regex perfectly, but we can look for suspicious patterns
                        lines = content.split('\n')
                        for i, line in enumerate(lines):
                            if ': str' in line and '=' not in line and 'def ' not in line:
                                # Field definition like "name: str"
                                self.log_issue('WARNING', 'PYDANTIC', "String field without max_length validation", path, i+1)
                except Exception:
                    pass

    def check_7_pypi_packages(self):
        """Verify packages in requirements.txt exist on PyPI."""
        print("\n[7/10] Checking PyPI packages...")
        req_files = list(self.root.glob('requirements*.txt'))
        
        for req_file in req_files:
            try:
                with open(req_file, 'r') as f:
                    for line in f:
                        line = line.strip()
                        if not line or line.startswith('#'): continue
                        
                        # Parse package name
                        pkg_name = re.split(r'[=<>!]', line)[0].strip()
                        if not pkg_name: continue
                        
                        # Skip local or git installs
                        if pkg_name.startswith('.') or 'git+' in line: continue

                        # Check PyPI (simple HEAD request)
                        url = f"https://pypi.org/pypi/{pkg_name}/json"
                        try:
                            req = urllib.request.Request(url, method='HEAD')
                            urllib.request.urlopen(req)
                        except urllib.error.HTTPError as e:
                            if e.code == 404:
                                self.log_issue('CRITICAL', 'DEPENDENCY', f"Package '{pkg_name}' not found on PyPI", req_file)
                            else:
                                pass # Ignore other errors (network etc)
                        except Exception:
                            pass
            except Exception:
                pass

    def check_8_all_md_links(self):
        """Check EVERY link in ALL .md files."""
        print("\n[8/10] Checking all Markdown links...")
        md_files = list(self.root.rglob('*.md'))
        
        for md_file in md_files:
            if self.is_ignored(md_file): continue
            
            try:
                content = md_file.read_text(errors='ignore')
                # Find [text](link)
                links = re.findall(r'\]\(([^)]+)\)', content)
                
                for link in links:
                    link = link.strip()
                    if link.startswith('http') or link.startswith('mailto:') or link.startswith('#'):
                        continue
                    
                    # Local link
                    # Remove anchor
                    link_path = link.split('#')[0]
                    if not link_path: continue
                    
                    # Resolve path
                    if link_path.startswith('/'):
                        # Absolute from root
                        target = self.root / link_path.lstrip('/')
                    else:
                        # Relative
                        target = (md_file.parent / link_path).resolve()
                    
                    if not target.exists():
                        self.log_issue('CRITICAL', 'BROKEN_LINK', f"Broken link: {link}", md_file)
            except Exception:
                pass

    def check_9_file_references(self):
        """Check if files mentioned in code/docs actually exist."""
        print("\n[9/10] Checking file references in text...")
        # This is a heuristic check. We look for strings that look like file paths.
        # Focus on READMEs and scripts
        
        files_to_scan = list(self.root.rglob('*.md')) + list(self.root.rglob('*.py')) + list(self.root.rglob('*.sh'))
        
        for f in files_to_scan:
            if self.is_ignored(f): continue
            
            try:
                content = f.read_text(errors='ignore')
                # Look for paths like "src/main.py", "docs/guide.md"
                # Regex: word chars, slashes, dots. At least one slash.
                candidates = re.findall(r'(?:\.?/)?[\w\-\.]+(?:/[\w\-\.]+)+\.\w+', content)
                
                for cand in candidates:
                    # Skip common false positives
                    if 'http' in cand or 'github.com' in cand or '{' in cand: continue
                    
                    # Try to resolve
                    if cand.startswith('/'):
                        target = self.root / cand.lstrip('/')
                    else:
                        target = (f.parent / cand).resolve()
                        
                    # Also try relative to root if relative failed
                    if not target.exists() and not cand.startswith('/'):
                        target_root = self.root / cand
                        if target_root.exists():
                            target = target_root

                    # If it looks like a file path but doesn't exist
                    if not target.exists():
                        # Filter out likely non-files (e.g. URLs without http, or just text)
                        if any(x in cand for x in ['.py', '.md', '.txt', '.json', '.yml', '.sh']):
                             # Only report if it really looks like a specific file reference
                             # Reduce noise by checking if it's a known file extension
                             self.log_issue('WARNING', 'MISSING_FILE_REF', f"Referenced file not found: {cand}", f)

            except Exception:
                pass

    def check_10_documentation_completeness(self):
        """Verify every module has docs."""
        print("\n[10/10] Checking documentation completeness...")
        # Check if src/ folders have corresponding docs/
        src_dir = self.root / 'src'
        docs_dir = self.root / 'docs'
        
        if src_dir.exists():
            for item in src_dir.iterdir():
                if item.is_dir() and not item.name.startswith('__'):
                    # Expect a doc file or folder
                    # e.g. src/api -> docs/api.md or docs/api/README.md or docs/0X-api...
                    
                    found = False
                    # Search in docs
                    for doc in docs_dir.rglob('*'):
                        if item.name.lower() in doc.name.lower():
                            found = True
                            break
                    
                    if not found:
                        self.log_issue('WARNING', 'MISSING_DOCS', f"No documentation found for module: {item.name}", item)

    def run(self):
        print("Starting DEEP VERIFICATION V3...")
        self.check_1_hidden_folders()
        self.check_2_private_paths()
        self.check_3_security_patterns()
        self.check_4_rate_limiting()
        self.check_5_timeouts()
        self.check_6_pydantic_validation()
        self.check_7_pypi_packages()
        self.check_8_all_md_links()
        self.check_9_file_references()
        self.check_10_documentation_completeness()
        
        print("\n" + "="*50)
        print("VERIFICATION SUMMARY")
        print("="*50)
        
        criticals = [i for i in self.issues if i['level'] == 'CRITICAL']
        warnings = [i for i in self.issues if i['level'] == 'WARNING']
        
        print(f"CRITICAL ISSUES: {len(criticals)}")
        print(f"WARNINGS: {len(warnings)}")
        
        if criticals:
            print("\n!!! CRITICAL ISSUES !!!")
            for i in criticals:
                print(f"- [{i['category']}] {i['message']} ({i['file']}:{i['line']})")
                
        if warnings:
            print("\n--- WARNINGS ---")
            for i in warnings[:20]: # Limit output
                print(f"- [{i['category']}] {i['message']} ({i['file']}:{i['line']})")
            if len(warnings) > 20:
                print(f"... and {len(warnings) - 20} more")

        return len(criticals)

if __name__ == '__main__':
    verifier = DeepVerifier()
    sys.exit(verifier.run())


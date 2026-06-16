import re
import subprocess


def run_command(command):
    try:
        subprocess.run(command, shell=True, check=True)
        print(f"[OK] Successfully ran: {command}")
    except subprocess.CalledProcessError as e:
        print(f"[FAIL] Failed to run: {command}")

def fix_isort():
    print("[1/3] Running isort...")
    run_command("isort src/ tests/")

def fix_with_flake8():
    print("[2/3] Running flake8 and applying fixes (F541, E722, W293)...")
    
    # Run flake8 and capture output
    try:
        result = subprocess.run(
            ["flake8", "src/", "tests/", "--format=default", "--max-line-length=120", "--ignore=E203,W503"], 
            capture_output=True, 
            text=True,
            encoding='utf-8' # Ensure utf-8
        )
    except FileNotFoundError:
        print("Error: flake8 not found. Please pip install flake8")
        return

    output = result.stdout
    
    # Parse output: path:line:col: code message
    issues = []
    for line in output.splitlines():
        m = re.match(r'([^:]+):(\d+):(\d+):\s*([A-Z]\d+)\s*(.*)', line)
        if m:
            issues.append({
                'path': m.group(1),
                'line': int(m.group(2)),
                'col': int(m.group(3)),
                'code': m.group(4),
                'msg': m.group(5)
            })
            
    print(f"Found {len(issues)} issues.")
    
    # Sort by path, then line DESCending to avoid shifting indices
    issues.sort(key=lambda x: (x['path'], -x['line']))
    
    current_file = None
    lines = []
    modified = False
    
    for i, issue in enumerate(issues):
        path = issue['path']
        line_idx = issue['line'] - 1
        code = issue['code']
        
        # Switch file
        if path != current_file:
            # Save previous file if modified
            if current_file and modified:
                try:
                    with open(current_file, 'w', encoding='utf-8') as f:
                        f.writelines(lines)
                    # print(f"Saved {current_file}")
                except Exception as e:
                    print(f"Error saving {current_file}: {e}")
            
            # Open new file
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    lines = f.readlines()
                current_file = path
                modified = False
            except Exception as e:
                print(f"Error opening {path}: {e}")
                current_file = None
                continue
        
        if not current_file or line_idx >= len(lines):
            continue
            
        line_content = lines[line_idx]
        new_line = line_content
        
        # --- Fix Logic ---
        
        if code == 'F541': # f-string missing placeholders
            # Replace f" with " and f' with '
            # Regex to find f" or f' not preceded by char (start of string)
            # Be careful not to match "af"
            # We know the column, but regex is simpler for line
            if 'f"' in line_content:
                new_line = line_content.replace('f"', '"', 1)
            elif "f'" in line_content:
                new_line = line_content.replace("f'", "'", 1)
                
        elif code == 'E722': # do not use bare 'except'
            # Only replace 'except:' with 'except Exception:'
            # Avoid 'except ValueError:'
            new_line = re.sub(r'except\s*:', 'except Exception:', line_content)
            
        elif code == 'W293': # blank line contains whitespace
            if line_content.strip() == "":
                new_line = '\n'
                
        elif code == 'W291': # trailing whitespace
            new_line = line_content.rstrip() + '\n'

        # ----------------
        
        if new_line != line_content:
            lines[line_idx] = new_line
            modified = True
            
    # Save last file
    if current_file and modified:
        try:
            with open(current_file, 'w', encoding='utf-8') as f:
                f.writelines(lines)
            # print(f"Saved {current_file}")
        except Exception as e:
            print(f"Error saving {current_file}: {e}")

    print("Flake8 fixes applied.")

def main():
    # Install isort if needed (fast check)
    try:
        subprocess.run(["isort", "--version"], capture_output=True)
    except FileNotFoundError:
        print("Installing isort...")
        subprocess.run("pip install isort", shell=True)

    fix_isort()
    fix_with_flake8()
    print("\nDone! Run 'git diff' to see changes.")

if __name__ == "__main__":
    main()

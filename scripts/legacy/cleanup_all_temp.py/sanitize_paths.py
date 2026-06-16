import re


def sanitize_file(filepath):
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Replace Windows paths
        content = re.sub(r'C:\\\\Users\\\\[a-zA-Z0-9_]+', r'C:\\\\Users\\\\User', content, flags=re.IGNORECASE)
        content = re.sub(r'C:\\Users\\[a-zA-Z0-9_]+', r'C:\\Users\\User', content, flags=re.IGNORECASE)
        
        # Replace Unix paths
        content = re.sub(r'/home/[a-zA-Z0-9_]+', r'/home/user', content)
        content = re.sub(r'/Users/[a-zA-Z0-9_]+', r'/Users/user', content)
        
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"Sanitized {filepath}")
    except Exception as e:
        print(f"Error sanitizing {filepath}: {e}")

files_to_sanitize = [
    'docs/research/constitution.md',
    'docs/stage-0/manual-sync.md',
    'repo_magnit_ansible/install_ragent/templates/srv1cv8@.service.j2'
]

for f in files_to_sanitize:
    sanitize_file(f)

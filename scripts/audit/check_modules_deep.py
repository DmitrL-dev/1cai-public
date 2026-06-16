
import os

MODULES_DIR = "m1cai_modules"
DOCS_DIR = "docs"
README_FILE = "m1cai_modules/README.md" # Проверим локальный README, если есть, или глобальный

def check_modules_deep():
    if not os.path.exists(MODULES_DIR):
        print(f"❌ Directory {MODULES_DIR} not found!")
        return

    modules = [f for f in os.listdir(MODULES_DIR) if f.endswith('.bsl')]
    
    print(f"Found {len(modules)} modules in {MODULES_DIR}")
    
    # Load documentation files
    doc_files = []
    for root, dirs, files in os.walk(DOCS_DIR):
        for file in files:
            if file.endswith(".md"):
                doc_files.append(os.path.join(root, file))
    
    # Check global README
    readme_content = ""
    if os.path.exists("README.md"):
        with open("README.md", "r", encoding="utf-8") as f:
            readme_content = f.read()
            
    # Check local README in modules dir
    local_readme_content = ""
    if os.path.exists(README_FILE):
        with open(README_FILE, "r", encoding="utf-8") as f:
            local_readme_content = f.read()
    elif os.path.exists("m1cai_modules/README.md"):
         with open("m1cai_modules/README.md", "r", encoding="utf-8") as f:
            local_readme_content = f.read()

    report = {}

    for module in modules:
        module_name = module
        module_path = os.path.join(MODULES_DIR, module)
        
        # 1. Check internal description (header)
        with open(module_path, "r", encoding="utf-8-sig", errors='replace') as f:
            content = f.read()
            has_header = len(content) > 0 and (content.strip().startswith("//") or content.strip().startswith("&"))
            # Simple check for comments at the top
            lines = content.split('\n')
            header_lines = [l for l in lines[:10] if l.strip().startswith("//")]
            has_description = len(header_lines) > 0
        
        # 2. Check documentation references
        found_in_docs = False
        found_doc_file = False
        doc_file_path = None
        
        # Search for module name (without extension) in docs
        name_no_ext = os.path.splitext(module)[0]
        
        for doc in doc_files:
            if name_no_ext in doc: # Filename match
                found_doc_file = True
                doc_file_path = doc
            
            with open(doc, "r", encoding="utf-8", errors='replace') as f:
                if name_no_ext in f.read():
                    found_in_docs = True

        # 3. Check in READMEs
        found_in_global_readme = name_no_ext in readme_content
        found_in_local_readme = name_no_ext in local_readme_content

        report[module] = {
            "has_header_description": has_description,
            "found_in_docs_content": found_in_docs,
            "has_dedicated_doc_file": found_doc_file,
            "found_in_global_readme": found_in_global_readme,
            "found_in_local_readme": found_in_local_readme,
            "doc_file": doc_file_path
        }

    # Print Report
    print("\n=== DEEP MODULE CHECK REPORT ===\n")
    print(f"{'Module':<30} | {'Header':<6} | {'Docs Ref':<6} | {'DocFile':<8} | {'README':<6}")
    print("-" * 80)
    
    issues_count = 0
    for module, status in report.items():
        ok = "[OK]"
        fail = "[FAIL]"
        
        header = ok if status["has_header_description"] else fail
        docs_ref = ok if status["found_in_docs_content"] else fail
        doc_file = ok if status["has_dedicated_doc_file"] else fail
        readme = ok if (status["found_in_global_readme"] or status["found_in_local_readme"]) else fail
        
        print(f"{module:<30} | {header:<6} | {docs_ref:<6} | {doc_file:<8} | {readme:<6}")
        
        if not (status["has_header_description"] and status["found_in_docs_content"] and (status["found_in_global_readme"] or status["found_in_local_readme"])):
            issues_count += 1

    print("-" * 80)
    if issues_count == 0:
        print("\n[OK] All modules passed the deep check.")
    else:
        print(f"\n[FAIL] {issues_count} modules failed the deep check (missing docs, header or readme ref).")

if __name__ == "__main__":
    check_modules_deep()


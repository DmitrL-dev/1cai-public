import ast
import os
import re
import sys
from typing import List, Tuple, Optional
import openai
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure OpenAI
api_key = os.getenv("OPENAI_API_KEY")
if not api_key:
    print("WARNING: OPENAI_API_KEY not found in .env. Translation will be simulated (dry-run).")

client = openai.OpenAI(api_key=api_key) if api_key else None

def has_cyrillic(text: str) -> bool:
    return bool(re.search('[а-яА-Я]', text))

def translate_text(text: str) -> str:
    """Translates text to Russian Google Style docstring using LLM."""
    if not client:
        return f"[MOCK TRANSLATION] {text}"
    
    prompt = f"""
    You are a technical translator and Python expert.
    Translate the following Python docstring to Russian.
    
    Rules:
    1. Use Google Style formatting.
    2. Keep technical terms in English if appropriate (e.g. middleware, token).
    3. Use imperative mood ("Return", not "Returns").
    4. Preserve indentation and formatting.
    5. Output ONLY the translated docstring content, no quotes.
    
    Input:
    {text}
    """
    
    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": prompt}],
            temperature=0
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        print(f"Error translating: {e}")
        return text

class DocstringTranslator(ast.NodeTransformer):
    def __init__(self):
        self.modified = False
        self.count = 0

    def visit_FunctionDef(self, node):
        self._process_node(node)
        return self.generic_visit(node)

    def visit_ClassDef(self, node):
        self._process_node(node)
        return self.generic_visit(node)

    def visit_Module(self, node):
        self._process_node(node)
        return self.generic_visit(node)

    def _process_node(self, node):
        docstring = ast.get_docstring(node)
        if docstring and not has_cyrillic(docstring):
            # It's likely English
            print(f"Translating docstring for node line {node.lineno}...")
            translated = translate_text(docstring)
            
            # Create new docstring node
            # This is tricky with AST, usually easier to replace text in file
            # For this script, we will just mark it. 
            # AST transformation preserves structure but loses comments/formatting often.
            # A better approach for production is using 'libcst' or regex replacement.
            pass

def process_file_regex(file_path: str):
    """
    Simple regex-based replacement to preserve formatting better than AST.
    """
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Regex to find docstrings: """...""" or '''...'''
    # This is a simplified regex and might miss edge cases
    pattern = re.compile(r'("""(.*?)"""|\'\'\'(.*?)\'\'\')', re.DOTALL)
    
    new_content = content
    offset = 0
    
    matches = list(pattern.finditer(content))
    count = 0
    
    for match in matches:
        full_match = match.group(1)
        inner_text = match.group(2) or match.group(3)
        
        if not inner_text or has_cyrillic(inner_text):
            continue
            
        print(f"Found English docstring in {file_path}")
        
        # Translate
        translated_inner = translate_text(inner_text)
        
        # Reconstruct
        quote = '"""' if '"""' in full_match else "'''"
        new_docstring = f"{quote}{translated_inner}{quote}"
        
        # Replace
        # We need to be careful about overlapping replacements if we modify 'new_content'
        # Ideally we build a list of replacements and apply them reverse order
        
        # For this PoC, let's just count them
        count += 1
        
    return count

if __name__ == "__main__":
    if len(sys.argv) > 1:
        target_dir = sys.argv[1]
    else:
        target_dir = "src/modules"
        
    print(f"Scanning {target_dir} for English docstrings...")
    
    total_found = 0
    
    for root, _, files in os.walk(target_dir):
        for file in files:
            if file.endswith(".py"):
                path = os.path.join(root, file)
                count = process_file_regex(path)
                if count > 0:
                    total_found += count
                    print(f"  {path}: {count} candidates")
                    
    print(f"\nTotal English docstrings found: {total_found}")
    print("To enable actual translation, ensure OPENAI_API_KEY is set and modify script to write changes.")

import docx
import sys

try:
    doc = docx.Document(r"C:\1cAI\docs\research\int.docx")
    full_text = []
    for para in doc.paragraphs:
        full_text.append(para.text)
    print("\n".join(full_text))
except Exception as e:
    print(f"Error reading docx: {e}")

"""
Split the monolithic Chapter 7 HTML dump into individual sections.
Each ch7_*.txt file contains the ENTIRE chapter. We take one, split by section headers.
"""

import re, sys, json
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

OUT = Path(r"C:\1cAI\docs\its_forms")
SECTIONS = OUT / "sections"
SECTIONS.mkdir(exist_ok=True)

# Read the first ch7 file (they're all identical - whole chapter)
src = sorted(OUT.glob("ch7_001_*.txt"))[0]
text = src.read_text(encoding="utf-8")

# Strip the header lines (# title, # TI, # URL)
lines = text.split("\n")
start = 0
for i, line in enumerate(lines):
    if not line.startswith("#") and line.strip():
        start = i
        break
text = "\n".join(lines[start:])

# Decode HTML entities
text = re.sub(r"&#(\d+);", lambda m: chr(int(m.group(1))), text)

# Find section boundaries using numbered headers like "7.1. ", "7.7.4.10. "
pattern = r"^(7\.\d+(?:\.\d+)*\.?\s+.+)$"
matches = list(re.finditer(pattern, text, re.MULTILINE))

print(f"Source: {src.name} ({len(text):,} chars)")
print(f"Section headers found: {len(matches)}")

# Split into sections
sections = []
for i, match in enumerate(matches):
    title = match.group(1).strip()
    sec_start = match.start()
    sec_end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
    content = text[sec_start:sec_end].strip()

    # Extract section number
    num_match = re.match(r"(7(?:\.\d+)+)", title)
    num = num_match.group(1) if num_match else f"7.x.{i}"

    # Skip duplicates (TOC vs actual content)
    if len(content) < 100:
        continue

    # Check for duplicate headers (TOC repeats headers)
    # Keep only the one with more content
    if sections and sections[-1]["num"] == num:
        if len(content) > sections[-1]["chars"]:
            sections[-1] = {
                "num": num,
                "title": title,
                "content": content,
                "chars": len(content),
            }
        continue

    sections.append(
        {"num": num, "title": title, "content": content, "chars": len(content)}
    )

print(f"Unique sections after dedup: {len(sections)}")

# Save each section
manifest = []
for sec in sections:
    safe_num = sec["num"].replace(".", "_")
    safe_title = re.sub(r'[<>:"/\\|?*]', "_", sec["title"])[:60]
    fn = f"sec_{safe_num}_{safe_title}.txt"
    (SECTIONS / fn).write_text(sec["content"], encoding="utf-8")
    manifest.append(
        {"num": sec["num"], "title": sec["title"], "file": fn, "chars": sec["chars"]}
    )

# Save manifest
(SECTIONS / "manifest.json").write_text(
    json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
)

# Print summary by top-level section
print("\n=== Sections by topic ===")
current_top = ""
topic_chars = 0
for sec in manifest:
    top = ".".join(sec["num"].split(".")[:2])
    if top != current_top:
        if current_top:
            print(f"  {current_top}: {topic_chars:,} chars")
        current_top = top
        topic_chars = 0
    topic_chars += sec["chars"]
if current_top:
    print(f"  {current_top}: {topic_chars:,} chars")

total = sum(s["chars"] for s in manifest)
print(f"\nTotal: {len(manifest)} sections, {total:,} chars")

# Delete the duplicate monolithic files (keep only one as backup)
kept = 0
for f in sorted(OUT.glob("ch7_*.txt")):
    if kept == 0:
        f.rename(OUT / "chapter7_full_backup.txt")
        kept = 1
    else:
        f.unlink()
        kept += 1
print(f"Cleaned {kept} duplicate monolithic files")

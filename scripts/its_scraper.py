"""
ITS 1C Form Documentation Scraper
Extracts Chapter 7 (Forms) + Syntax Helper form types from its.1c.ru
"""

import requests
import re
import os
import sys
import time
import json
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")

OUT_DIR = Path(r"C:\1cAI\docs\its_forms")
OUT_DIR.mkdir(parents=True, exist_ok=True)

SESSION = requests.Session()
SESSION.headers.update(
    {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept-Language": "ru-RU,ru;q=0.9",
    }
)


def fetch(url: str, retries: int = 3, timeout: int = 30) -> str:
    """Fetch URL with retries and proper encoding."""
    for attempt in range(retries):
        try:
            r = SESSION.get(url, timeout=timeout)
            r.encoding = "windows-1251"
            return r.text
        except Exception as e:
            print(f"  [RETRY {attempt + 1}/{retries}] {url}: {e}", file=sys.stderr)
            time.sleep(2 * (attempt + 1))
    return ""


def extract_text(html: str) -> str:
    """Extract clean text from HTML, preserving structure."""
    # Remove scripts and styles
    text = re.sub(r"<script[^>]*>.*?</script>", "", html, flags=re.DOTALL)
    text = re.sub(r"<style[^>]*>.*?</style>", "", text, flags=re.DOTALL)
    # Convert <br> and block elements to newlines
    text = re.sub(r"<br\s*/?>", "\n", text)
    text = re.sub(r"</(p|div|tr|li|h[1-6]|dt|dd|table)>", "\n", text)
    text = re.sub(r"<(p|div|tr|li|h[1-6]|dt|dd)[^>]*>", "\n", text)
    # Convert <td> to tab separator
    text = re.sub(r"<td[^>]*>", "\t", text)
    # Remove remaining HTML tags
    text = re.sub(r"<[^>]+>", "", text)
    # Decode HTML entities
    text = text.replace("&nbsp;", " ")
    text = text.replace("&lt;", "<")
    text = text.replace("&gt;", ">")
    text = text.replace("&amp;", "&")
    text = text.replace("&quot;", '"')
    text = text.replace("&#39;", "'")
    # Clean up whitespace
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n[ \t]+", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def extract_content_area(html: str) -> str:
    """Extract only the main content area from ITS page."""
    # ITS wraps content in specific div structures
    # Try to find the main content block
    match = re.search(r'<div[^>]*class="[^"]*content[^"]*"[^>]*>(.*)', html, re.DOTALL)
    if match:
        return match.group(1)
    # Fallback: look for the documentation text between navigation elements
    match = re.search(r"<!-- content -->(.*?)<!-- /content -->", html, re.DOTALL)
    if match:
        return match.group(1)
    # Another fallback: find the main text block
    match = re.search(
        r'<div[^>]*id="(?:textbody|doc_body|article)"[^>]*>(.*?)</div>', html, re.DOTALL
    )
    if match:
        return match.group(1)
    return html


def scrape_chapter7_toc():
    """Get all TI bookmark IDs for Chapter 7 (Forms)."""
    print("=== Scraping Chapter 7 TOC ===")
    html = fetch("https://its.1c.ru/db/v8327doc/content/52/hdoc")
    if not html:
        print("ERROR: Could not fetch Chapter 7 TOC")
        return []

    # Extract all TI references
    ti_ids = sorted(set(re.findall(r"TI(\d+)", html)))
    print(f"Found {len(ti_ids)} TI references in Chapter 7")

    # Also extract the TOC text
    text = extract_text(html)
    toc_file = OUT_DIR / "00_chapter7_toc.txt"
    toc_file.write_text(text, encoding="utf-8")
    print(f"Saved TOC to {toc_file}")

    return ti_ids


def scrape_ti_topic(ti_id: str, index: int, total: int) -> dict:
    """Scrape a single TI topic."""
    url = f"https://its.1c.ru/db/v8327doc/bookmark/dev/TI{ti_id}"
    html = fetch(url)
    if not html:
        return {"ti": ti_id, "title": "ERROR", "error": "fetch failed"}

    # Extract title
    title_match = re.search(r"<title>([^<]+)</title>", html)
    title = title_match.group(1).strip() if title_match else f"TI{ti_id}"
    # Clean title
    title = title.replace(
        " :: Руководство разработчика :: 1С:Предприятие 8.3.27. Документация", ""
    )
    title = title.strip()

    # Extract content
    content = extract_content_area(html)
    text = extract_text(content)

    # Skip if too short (probably a redirect or error page)
    if len(text) < 50:
        print(f"  [{index}/{total}] TI{ti_id}: SKIP (too short: {len(text)} chars)")
        return {"ti": ti_id, "title": title, "text": text, "chars": len(text)}

    # Save to file
    safe_title = re.sub(r'[<>:"/\\|?*]', "_", title)[:80]
    filename = f"ti_{ti_id}_{safe_title}.txt"
    filepath = OUT_DIR / filename
    filepath.write_text(
        f"# {title}\n# URL: {url}\n# TI: {ti_id}\n\n{text}", encoding="utf-8"
    )

    print(f"  [{index}/{total}] TI{ti_id}: {title} ({len(text)} chars)")
    return {"ti": ti_id, "title": title, "file": filename, "chars": len(text)}


def scrape_syntax_helper():
    """Scrape syntax helper for form-related types."""
    print("\n=== Scraping Syntax Helper ===")

    # Key search terms for form types in syntax helper
    search_terms = [
        "УправляемаяФорма",
        "ПолеФормы",
        "ГруппаФормы",
        "КнопкаФормы",
        "ДекорацияФормы",
        "РеквизитФормы",
        "КомандаФормы",
        "ВидПоляФормы",
        "ВидГруппыФормы",
        "ВидДекорацииФормы",
        "ТипКнопкиФормы",
        "ГруппировкаПодчиненныхЭлементовФормы",
        "ОтображениеСтраниц",
        "УсловноеОформлениеФормы",
        "ОтображениеПодсказки",
        "ПоложениеЗаголовкаЭлементаФормы",
        "ВидНадписиФормы",
        "ПоложениеКоманднойПанели",
        "ВертикальноеПоложениеЭлемента",
        "ГоризонтальноеПоложениеЭлемента",
        "РастягиваниеПоГоризонтали",
        "РастягиваниеПоВертикали",
        "ДинамическийСписок",
        "ТаблицаФормы",
        "ДанныеФормыСтруктура",
        "ДанныеФормыКоллекция",
        "ДанныеФормыДерево",
        "ИзменитьРеквизиты",
        "ЭлементыФормы",
    ]

    results = []
    for i, term in enumerate(search_terms):
        print(f"  Searching [{i + 1}/{len(search_terms)}]: {term}")
        url = f"https://its.1c.ru/db/v8327doc/search?query={term}"
        html = fetch(url)
        if not html:
            continue

        # Extract search results
        matches = re.findall(
            r'href="(/db/v8327doc/content/(\d+)/hdoc)"[^>]*>([^<]+)', html
        )

        for href, cid, title in matches[:5]:
            title = title.strip()
            if term.lower() in title.lower() or "форм" in title.lower():
                results.append(
                    {
                        "term": term,
                        "content_id": cid,
                        "title": title,
                        "url": f"https://its.1c.ru{href}",
                    }
                )

        # Also search in syntax helper DB (section 5)
        url2 = f"https://its.1c.ru/db/v8327doc/browse/13/-1/5"
        # Small delay to be nice to the server
        time.sleep(0.3)

    # Deduplicate by content_id
    seen = set()
    unique_results = []
    for r in results:
        if r["content_id"] not in seen:
            seen.add(r["content_id"])
            unique_results.append(r)

    print(f"\nFound {len(unique_results)} unique syntax helper entries")

    # Now fetch each unique result
    for i, r in enumerate(unique_results):
        print(f"  Fetching [{i + 1}/{len(unique_results)}]: {r['title']}")
        html = fetch(r["url"])
        if html:
            content = extract_content_area(html)
            text = extract_text(content)
            safe_title = re.sub(r'[<>:"/\\|?*]', "_", r["title"])[:80]
            filename = f"syntax_{r['content_id']}_{safe_title}.txt"
            filepath = OUT_DIR / filename
            filepath.write_text(
                f"# {r['title']}\n# URL: {r['url']}\n# Search term: {r['term']}\n\n{text}",
                encoding="utf-8",
            )
            r["file"] = filename
            r["chars"] = len(text)
        time.sleep(0.3)

    return unique_results


def scrape_v85_changes():
    """Scrape 8.5 form-related changes."""
    print("\n=== Scraping 8.5 Changes ===")

    # Try to access 8.5.1 documentation
    url = "https://its.1c.ru/db/v8327doc/content/52/hdoc"
    html = fetch(url)
    if not html:
        return

    # Check if there's a version selector for 8.5
    # The page showed version links: 8.5.1, 8.3.27, etc.
    # Try the 8.5 version URL pattern
    for v85_db in ["v851doc", "v85doc", "v8doc"]:
        url = f"https://its.1c.ru/db/{v85_db}/"
        html = fetch(url, retries=1, timeout=10)
        if html and len(html) > 1000:
            title = re.search(r"<title>([^<]+)</title>", html)
            if title:
                print(f"  Found 8.5 DB: {v85_db} -> {title.group(1)}")
                break

    # The version selector on the page suggests we can switch versions
    # Let's try scraping Chapter 7 with 8.5.1 version selected
    # ITS typically uses a query parameter or different DB for versions


def scrape_appendix11():
    """Scrape Appendix 11 - form element naming rules."""
    print("\n=== Scraping Appendix 11 (Element Naming Rules) ===")
    url = "https://its.1c.ru/db/v8327doc/content/95/hdoc"
    html = fetch(url)
    if html:
        content = extract_content_area(html)
        text = extract_text(content)
        filepath = OUT_DIR / "appendix11_element_naming_rules.txt"
        filepath.write_text(
            f"# Приложение 11. Правила автоматического формирования имен элементов формы\n# URL: {url}\n\n{text}",
            encoding="utf-8",
        )
        print(f"  Saved ({len(text)} chars)")


def scrape_chapter7_sections():
    """Scrape key Chapter 7 sections by content ID."""
    print("\n=== Scraping Key Chapter 7 Sections ===")

    # These are the key sections we identified from the TOC
    # Content IDs found via the browse structure
    # We'll scrape sections 7.7 (Elements) and 7.9 (Programmatic) in detail

    # First, get all content page IDs by following the TOC links
    url = "https://its.1c.ru/db/v8327doc/content/52/hdoc"
    html = fetch(url)
    if not html:
        return

    # The page itself contains all the section text! It's a long single page.
    # Let's just save the whole thing properly
    text = extract_text(html)
    filepath = OUT_DIR / "chapter7_forms_FULL.txt"
    filepath.write_text(text, encoding="utf-8")
    print(f"  Saved full Chapter 7 ({len(text)} chars)")

    # Now let's also try individual sub-pages
    # ITS often has content in multiple pages linked by TI bookmarks
    ti_ids = sorted(set(re.findall(r"TI(\d+)", html)))
    return ti_ids


def main():
    print("=" * 60)
    print("ITS 1C Form Documentation Scraper")
    print("=" * 60)

    # 1. Get Chapter 7 full content and TI IDs
    ti_ids = scrape_chapter7_sections()
    if not ti_ids:
        ti_ids = scrape_chapter7_toc()

    # 2. Scrape each TI topic
    print(f"\n=== Scraping {len(ti_ids)} TI Topics ===")
    manifest = []
    for i, ti_id in enumerate(ti_ids):
        result = scrape_ti_topic(ti_id, i + 1, len(ti_ids))
        manifest.append(result)
        # Be nice to the server
        time.sleep(0.5)

    # 3. Scrape syntax helper
    syntax_results = scrape_syntax_helper()

    # 4. Scrape Appendix 11
    scrape_appendix11()

    # 5. Check 8.5 changes
    scrape_v85_changes()

    # 6. Save manifest
    manifest_data = {
        "chapter7_topics": manifest,
        "syntax_helper": syntax_results,
        "total_topics": len(manifest),
        "total_syntax": len(syntax_results),
        "scraped_at": time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    manifest_file = OUT_DIR / "manifest.json"
    manifest_file.write_text(
        json.dumps(manifest_data, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    # Summary
    total_chars = sum(r.get("chars", 0) for r in manifest)
    total_files = sum(1 for r in manifest if r.get("file"))
    print(f"\n{'=' * 60}")
    print(f"DONE!")
    print(f"  Topics scraped: {total_files}/{len(ti_ids)}")
    print(f"  Syntax entries: {len(syntax_results)}")
    print(f"  Total chars: {total_chars:,}")
    print(f"  Output dir: {OUT_DIR}")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()

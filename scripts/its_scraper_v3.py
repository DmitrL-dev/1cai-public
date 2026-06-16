"""
ITS 1C Form Documentation Scraper v3
Uses Playwright (headless browser) because ITS loads content via JavaScript/AJAX.
"""

import os, re, sys, time, json
from pathlib import Path
from playwright.sync_api import sync_playwright
from dotenv import load_dotenv

load_dotenv()

sys.stdout.reconfigure(encoding="utf-8")

OUT = Path(r"C:\1cAI\docs\its_forms")
OUT.mkdir(parents=True, exist_ok=True)

# Clean old files from failed runs
for f in OUT.glob("ti_*.txt"):
    f.unlink()


def clean(text):
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n[ \t]+", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def main():
    print("ITS Scraper v3 (Playwright)")

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        ctx = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            locale="ru-RU",
        )
        page = ctx.new_page()

        # === LOGIN ===
        print("Logging in...")
        page.goto(
            "https://login.1c.ru/login?service=https://its.1c.ru/login/?action=aftercheck&provider=login",
            wait_until="networkidle",
            timeout=30000,
        )
        page.fill('input[name="username"]', os.environ.get("ITS_USERNAME", ""))
        page.fill('input[name="password"]', os.environ.get("ITS_PASSWORD", ""))
        page.click('input[name="submit"]')
        page.wait_for_load_state("networkidle", timeout=30000)
        print(f"  Logged in, URL: {page.url[:60]}")

        # === CHAPTER 7 (Forms) - get all sub-section links ===
        print("Loading Chapter 7 TOC...")
        page.goto(
            "https://its.1c.ru/db/v8327doc/content/52/hdoc",
            wait_until="networkidle",
            timeout=30000,
        )
        time.sleep(2)

        # Extract all internal links from the TOC
        toc_links = page.eval_on_selector_all(
            'a[href*="/db/v8327doc/"]',
            """els => els.map(e => ({href: e.href, text: e.textContent.trim()}))
               .filter(x => x.text.length > 3 && x.href.includes("/content/"))""",
        )

        # Deduplicate by href
        seen = set()
        unique_links = []
        for link in toc_links:
            if link["href"] not in seen:
                seen.add(link["href"])
                unique_links.append(link)

        print(f"  Found {len(unique_links)} unique section links")

        # Save TOC
        toc_text = page.inner_text("body")
        (OUT / "chapter7_toc.txt").write_text(clean(toc_text), encoding="utf-8")

        # === SCRAPE EACH SECTION ===
        results = []
        total = len(unique_links)

        for i, link in enumerate(unique_links, 1):
            url = link["href"]
            label = link["text"][:60]

            try:
                page.goto(url, wait_until="networkidle", timeout=30000)
                time.sleep(1)

                # Get the main content text
                text = page.inner_text("body")
                text = clean(text)

                if len(text) < 100:
                    continue

                # Extract content ID from URL
                cid_match = re.search(r"/content/(\d+)/", url)
                cid = cid_match.group(1) if cid_match else str(i)

                safe = re.sub(r'[<>:"/\\|?*]', "_", label)[:60]
                fn = f"ch7_{cid}_{safe}.txt"
                (OUT / fn).write_text(
                    f"# {label}\n# URL: {url}\n\n{text}", encoding="utf-8"
                )

                results.append(
                    {"cid": cid, "title": label, "file": fn, "chars": len(text)}
                )

                if i % 10 == 0 or i == total:
                    print(f"  [{i}/{total}] {label} ({len(text)}ch)")

            except Exception as e:
                print(f"  [{i}/{total}] ERROR: {label}: {str(e)[:60]}")
                continue

            time.sleep(0.5)

        # === SYNTAX HELPER - Form types ===
        print("Syntax helper...")

        syntax_searches = [
            "УправляемаяФорма",
            "ПолеФормы",
            "ГруппаФормы",
            "КнопкаФормы",
            "ДекорацияФормы",
            "РеквизитФормы",
            "КомандаФормы",
            "ВидПоляФормы",
            "ВидГруппыФормы",
            "ТаблицаФормы",
            "ДанныеФормыСтруктура",
            "ДанныеФормыКоллекция",
            "ДанныеФормыДерево",
            "ЭлементыФормы",
            "ВсеЭлементыФормы",
            "ДинамическийСписок",
            "УсловноеОформление",
            "ВидДекорацииФормы",
            "ГруппировкаПодчиненныхЭлементовФормы",
            "ОтображениеСтраниц",
            "ПоложениеЗаголовкаЭлементаФормы",
            "ПоложениеКоманднойПанели",
            "РежимРедактированияКолонки",
        ]

        # Navigate to syntax helper section
        page.goto(
            "https://its.1c.ru/db/v8327doc/browse/13/-1/5",
            wait_until="networkidle",
            timeout=30000,
        )
        time.sleep(2)

        sh_text = page.inner_text("body")
        (OUT / "syntax_helper_index.txt").write_text(clean(sh_text), encoding="utf-8")

        # Get all content links from syntax helper
        sh_links = page.eval_on_selector_all(
            'a[href*="/db/v8327doc/content/"]',
            """els => els.map(e => ({href: e.href, text: e.textContent.trim()}))
               .filter(x => x.text.length > 2)""",
        )

        # Filter for form-related
        form_kw = [
            "форм",
            "элемент",
            "управляем",
            "реквизит",
            "команд",
            "декорац",
            "кнопк",
            "группа",
            "таблиц",
            "поле",
            "оформлен",
            "динамическ",
            "список",
            "дерево",
            "коллекци",
        ]
        form_sh = [l for l in sh_links if any(k in l["text"].lower() for k in form_kw)]

        # Deduplicate
        seen2 = set()
        form_sh_unique = []
        for l in form_sh:
            if l["href"] not in seen2:
                seen2.add(l["href"])
                form_sh_unique.append(l)

        print(f"  Found {len(form_sh_unique)} form-related syntax entries")

        syntax_results = []
        for i, link in enumerate(form_sh_unique, 1):
            try:
                page.goto(link["href"], wait_until="networkidle", timeout=30000)
                time.sleep(1)
                text = clean(page.inner_text("body"))
                if len(text) < 100:
                    continue

                cid_match = re.search(r"/content/(\d+)/", link["href"])
                cid = cid_match.group(1) if cid_match else str(i)
                safe = re.sub(r'[<>:"/\\|?*]', "_", link["text"])[:60]
                fn = f"syntax_{cid}_{safe}.txt"
                (OUT / fn).write_text(
                    f"# {link['text']}\n# URL: {link['href']}\n\n{text}",
                    encoding="utf-8",
                )
                syntax_results.append(
                    {"cid": cid, "title": link["text"], "file": fn, "chars": len(text)}
                )

                if i % 5 == 0:
                    print(f"  [{i}/{len(form_sh_unique)}] {link['text'][:40]}")
            except Exception as e:
                continue
            time.sleep(0.5)

        # === APPENDIX 11 ===
        print("Appendix 11...")
        try:
            page.goto(
                "https://its.1c.ru/db/v8327doc/content/95/hdoc",
                wait_until="networkidle",
                timeout=30000,
            )
            time.sleep(1)
            text = clean(page.inner_text("body"))
            (OUT / "appendix11_naming.txt").write_text(text, encoding="utf-8")
            print(f"  OK ({len(text)}ch)")
        except:
            pass

        # === 8.5 DOCS ===
        print("8.5 docs...")
        try:
            page.goto(
                "https://its.1c.ru/db/v851doc/", wait_until="networkidle", timeout=30000
            )
            time.sleep(2)
            text = clean(page.inner_text("body"))
            (OUT / "v85_index.txt").write_text(text, encoding="utf-8")
            print(f"  8.5 index: {len(text)}ch")

            # Try to find forms chapter in 8.5
            v85_links = page.eval_on_selector_all(
                'a[href*="/db/v851doc/content/"]',
                """els => els.map(e => ({href: e.href, text: e.textContent.trim()}))
                   .filter(x => x.text.toLowerCase().includes('форм'))""",
            )
            if v85_links:
                print(f"  Found {len(v85_links)} form-related 8.5 links")
                for link in v85_links[:5]:
                    try:
                        page.goto(link["href"], wait_until="networkidle", timeout=30000)
                        time.sleep(1)
                        text = clean(page.inner_text("body"))
                        cid = re.search(r"/content/(\d+)/", link["href"]).group(1)
                        safe_name = re.sub(r'[<>:"/\\|?*]', "_", link["text"])[:40]
                        fn = f"v85_{cid}_{safe_name}.txt"
                        (OUT / fn).write_text(text, encoding="utf-8")
                    except:
                        pass
                    time.sleep(0.5)
        except Exception as e:
            print(f"  8.5: {str(e)[:60]}")

        browser.close()

    # === MANIFEST ===
    manifest = {
        "chapter7": results,
        "syntax": syntax_results,
        "stats": {
            "ch7_sections": len(results),
            "ch7_chars": sum(r.get("chars", 0) for r in results),
            "syntax_entries": len(syntax_results),
            "syntax_chars": sum(r.get("chars", 0) for r in syntax_results),
        },
        "scraped_at": time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    (OUT / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    s = manifest["stats"]
    print(
        f"\nDONE: {s['ch7_sections']} sections ({s['ch7_chars']:,}ch) + {s['syntax_entries']} syntax ({s['syntax_chars']:,}ch)"
    )


if __name__ == "__main__":
    main()

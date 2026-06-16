"""
ITS 1C Form Documentation Scraper v4
Strategy: Playwright for login + URL collection, requests for fast content fetch.
ITS is an SPA - TOC anchors resolve to /db/content/v8327doc/src/... direct HTML files.
"""

import os, re, sys, time, json
from pathlib import Path
from urllib.parse import unquote
import requests as req
from dotenv import load_dotenv

load_dotenv()

sys.stdout.reconfigure(encoding="utf-8")

OUT = Path(r"C:\1cAI\docs\its_forms")
OUT.mkdir(parents=True, exist_ok=True)

# Clean old ti_ files
for f in OUT.glob("ti_*.txt"):
    f.unlink()
for f in OUT.glob("ch7_*.txt"):
    f.unlink()
for f in OUT.glob("syntax_*.txt"):
    f.unlink()


def clean(html):
    t = re.sub(r"<script[^>]*>.*?</script>", "", html, flags=re.DOTALL)
    t = re.sub(r"<style[^>]*>.*?</style>", "", t, flags=re.DOTALL)
    t = re.sub(r"<br\s*/?>", "\n", t)
    t = re.sub(r"</(p|div|tr|li|h[1-6]|dt|dd|table|pre)>", "\n", t)
    t = re.sub(r"<(p|div|tr|li|h[1-6]|dt|dd)[^>]*>", "\n", t)
    t = re.sub(r"<td[^>]*>", "\t", t)
    t = re.sub(r"<[^>]+>", "", t)
    for old, new in [
        ("&nbsp;", " "),
        ("&lt;", "<"),
        ("&gt;", ">"),
        ("&amp;", "&"),
        ("&quot;", '"'),
        ("&#39;", "'"),
    ]:
        t = t.replace(old, new)
    t = re.sub(r"[ \t]+", " ", t)
    t = re.sub(r"\n[ \t]+", "\n", t)
    t = re.sub(r"\n{3,}", "\n\n", t)
    return t.strip()


def main():
    print("ITS Scraper v4")
    from playwright.sync_api import sync_playwright

    with sync_playwright() as pw:
        br = pw.chromium.launch(headless=True)
        ctx = br.new_context(locale="ru-RU")
        page = ctx.new_page()

        # === LOGIN ===
        print("Login...")
        page.goto(
            "https://login.1c.ru/login?service=https://its.1c.ru/login/?action=aftercheck&provider=login",
            wait_until="networkidle",
            timeout=30000,
        )
        page.fill('input[name="username"]', os.environ.get("ITS_USERNAME", ""))
        page.fill('input[name="password"]', os.environ.get("ITS_PASSWORD", ""))
        page.click('input[name="submit"]')
        page.wait_for_load_state("networkidle", timeout=30000)
        print(f"  OK: {page.url[:50]}")

        # === COLLECT COOKIES for requests ===
        cookies = ctx.cookies()
        session = req.Session()
        for c in cookies:
            session.cookies.set(c["name"], c["value"], domain=c["domain"])
        session.headers.update(
            {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            }
        )

        # === CHAPTER 7 - Collect all resolved URLs ===
        print("Chapter 7 TOC...")
        page.goto(
            "https://its.1c.ru/db/v8327doc/content/52/hdoc",
            wait_until="networkidle",
            timeout=30000,
        )
        time.sleep(3)

        # Get all TOC links with fully resolved href
        all_links = page.eval_on_selector_all(
            "a",
            """els => els.map(e => ({
            href: e.href,
            raw: e.getAttribute('href') || '',
            text: e.textContent.trim()
        })).filter(x => x.raw.startsWith('#TI') && x.text.length > 2)""",
        )

        # Deduplicate
        seen = set()
        toc = []
        for l in all_links:
            if l["raw"] not in seen:
                seen.add(l["raw"])
                toc.append(l)

        print(f"  {len(toc)} sections")

        # Check: do resolved hrefs point to content files?
        if toc:
            sample = toc[0]
            print(f"  Sample: {sample['text'][:40]} -> {sample['href'][:100]}")

        # === ALSO COLLECT SYNTAX HELPER URLS ===
        print("Syntax helper TOC...")
        page.goto(
            "https://its.1c.ru/db/v8327doc/browse/13/-1/5",
            wait_until="networkidle",
            timeout=30000,
        )
        time.sleep(2)

        sh_links = page.eval_on_selector_all(
            "a",
            """els => els.map(e => ({
            href: e.href,
            raw: e.getAttribute('href') || '',
            text: e.textContent.trim()
        })).filter(x => x.text.length > 2 && x.href.includes('/v8327doc/'))""",
        )

        seen2 = set()
        sh_toc = []
        for l in sh_links:
            if l["href"] not in seen2:
                seen2.add(l["href"])
                sh_toc.append(l)

        print(f"  {len(sh_toc)} entries total")

        br.close()

    # === FETCH CHAPTER 7 CONTENT via requests ===
    print(f"\nFetching {len(toc)} chapter 7 sections...")
    ch7_results = []

    for i, link in enumerate(toc, 1):
        url = link["href"]
        title = link["text"]

        try:
            r = session.get(url, timeout=30)
            # Try multiple encodings
            if r.apparent_encoding:
                r.encoding = r.apparent_encoding
            else:
                r.encoding = "windows-1251"

            text = clean(r.text)

            if len(text) < 50:
                continue

            ti = link["raw"].replace("#", "")
            safe = re.sub(r'[<>:"/\\|?*]', "_", title)[:50]
            fn = f"ch7_{i:03d}_{ti}_{safe}.txt"
            (OUT / fn).write_text(
                f"# {title}\n# TI: {ti}\n# URL: {url}\n\n{text}", encoding="utf-8"
            )

            ch7_results.append(
                {"i": i, "ti": ti, "title": title, "file": fn, "chars": len(text)}
            )

            if i % 20 == 0 or i == len(toc):
                print(f"  [{i}/{len(toc)}] {title[:40]}... ({len(text)}ch)")

        except Exception as e:
            print(f"  [{i}/{len(toc)}] ERR: {str(e)[:50]}")

        time.sleep(0.3)

    # === FETCH SYNTAX HELPER ===
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
        "данные",
    ]
    form_sh = [l for l in sh_toc if any(k in l["text"].lower() for k in form_kw)]

    print(f"\nFetching {len(form_sh)} syntax helper entries...")
    sh_results = []

    for i, link in enumerate(form_sh, 1):
        try:
            r = session.get(link["href"], timeout=30)
            r.encoding = r.apparent_encoding or "windows-1251"
            text = clean(r.text)
            if len(text) < 50:
                continue

            safe = re.sub(r'[<>:"/\\|?*]', "_", link["text"])[:50]
            fn = f"syntax_{i:03d}_{safe}.txt"
            (OUT / fn).write_text(
                f"# {link['text']}\n# URL: {link['href']}\n\n{text}", encoding="utf-8"
            )
            sh_results.append({"title": link["text"], "file": fn, "chars": len(text)})

            if i % 5 == 0:
                print(f"  [{i}/{len(form_sh)}] {link['text'][:40]}...")
        except:
            pass
        time.sleep(0.3)

    # === APPENDIX 11 ===
    print("Appendix 11...")
    try:
        r = session.get("https://its.1c.ru/db/v8327doc/content/95/hdoc", timeout=30)
        r.encoding = r.apparent_encoding or "windows-1251"
        text = clean(r.text)
        (OUT / "appendix11.txt").write_text(text, encoding="utf-8")
        print(f"  {len(text)}ch")
    except:
        pass

    # === MANIFEST ===
    ch7_chars = sum(r.get("chars", 0) for r in ch7_results)
    sh_chars = sum(r.get("chars", 0) for r in sh_results)

    manifest = {
        "chapter7": ch7_results,
        "syntax": sh_results,
        "stats": {
            "ch7_sections": len(ch7_results),
            "ch7_chars": ch7_chars,
            "syntax_entries": len(sh_results),
            "syntax_chars": sh_chars,
        },
        "scraped_at": time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    (OUT / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    print(
        f"\nDONE: {len(ch7_results)} ch7 ({ch7_chars:,}ch) + {len(sh_results)} syntax ({sh_chars:,}ch)"
    )


if __name__ == "__main__":
    main()

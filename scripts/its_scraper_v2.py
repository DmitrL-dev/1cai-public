"""
ITS 1C Form Documentation Scraper v2
With CAS SSO authentication, minimal console output
"""

import requests, re, os, sys, time, json
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")

OUT = Path(r"C:\1cAI\docs\its_forms")
OUT.mkdir(parents=True, exist_ok=True)

S = requests.Session()
S.headers.update(
    {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
)


def login():
    """Login to ITS via CAS SSO on login.1c.ru"""
    r = S.get(
        "https://login.1c.ru/login?service=https://its.1c.ru/login/?action=aftercheck&provider=login",
        timeout=15,
    )
    m = re.search(r'name="execution"\s+value="([^"]+)"', r.text)
    if not m:
        print("FATAL: no execution token")
        return False
    S.post(
        "https://login.1c.ru/login",
        data={
            "username": os.environ.get("ITS_USERNAME", ""),
            "password": os.environ.get("ITS_PASSWORD", ""),
            "execution": m.group(1),
            "_eventId": "submit",
            "submit": "Войти",
            "inviteCode": "",
            "inviteType": "",
            "geolocation": "",
        },
        timeout=15,
        allow_redirects=True,
    )
    # Verify
    r = S.get("https://its.1c.ru/db/v8327doc/bookmark/dev/TI000000391", timeout=15)
    r.encoding = "windows-1251"
    ok = len(r.text) > 20000
    print(f"Login: {'OK' if ok else 'FAIL'} ({len(r.text)} chars)")
    return ok


def fetch(url, retries=3):
    for i in range(retries):
        try:
            r = S.get(url, timeout=30)
            r.encoding = "windows-1251"
            return r.text
        except Exception as e:
            time.sleep(2 * (i + 1))
    return ""


def clean(html):
    """HTML -> clean text"""
    t = re.sub(r"<script[^>]*>.*?</script>", "", html, flags=re.DOTALL)
    t = re.sub(r"<style[^>]*>.*?</style>", "", t, flags=re.DOTALL)
    t = re.sub(r"<br\s*/?>", "\n", t)
    t = re.sub(r"</(p|div|tr|li|h[1-6]|dt|dd|table)>", "\n", t)
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


def get_title(html):
    m = re.search(r"<title>([^<]+)</title>", html)
    t = m.group(1).strip() if m else ""
    t = re.sub(r"\s*::\s*Руководство разработчика.*", "", t)
    t = re.sub(r"\s*::\s*Платформа.*", "", t)
    return t


def scrape_ti(ti_id, idx, total):
    """Scrape single TI topic, save to file, return metadata"""
    url = f"https://its.1c.ru/db/v8327doc/bookmark/dev/TI{ti_id}"
    html = fetch(url)
    if not html:
        return {"ti": ti_id, "err": "fetch_failed"}

    title = get_title(html)
    text = clean(html)

    # Remove the TOC/nav noise - find actual content
    # ITS pages have a content div; the TOC is duplicated on every page
    # We need to find the unique content section

    # The page has the chapter TOC + the actual section content
    # Look for the section heading that matches
    if len(text) < 100:
        return {"ti": ti_id, "title": title, "chars": len(text), "skip": True}

    safe = re.sub(r'[<>:"/\\|?*]', "_", title)[:60]
    fn = f"ti_{ti_id}_{safe}.txt"
    (OUT / fn).write_text(f"# {title}\n# TI: {ti_id}\n\n{text}", encoding="utf-8")

    if idx % 20 == 0 or idx == total:
        print(f"  [{idx}/{total}] {title[:50]}... ({len(text)}ch)")

    return {"ti": ti_id, "title": title, "file": fn, "chars": len(text)}


def scrape_syntax_helper():
    """Scrape syntax helper pages for form types"""
    print("Syntax helper...")

    # The syntax helper is in section 5 of v8327doc
    # Let's find it properly
    html = fetch("https://its.1c.ru/db/v8327doc/browse/13/-1/5")
    if not html:
        print("  Could not fetch syntax helper index")
        return []

    text = clean(html)
    (OUT / "syntax_helper_index.txt").write_text(text, encoding="utf-8")

    # Extract all content IDs from the syntax helper
    cids = re.findall(r'href="/db/v8327doc/content/(\d+)/hdoc"', html)
    print(f"  Found {len(cids)} content IDs in syntax helper")

    # Get each page, filter for form-related
    form_keywords = [
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
        "структур",
    ]

    results = []
    for i, cid in enumerate(cids):
        url = f"https://its.1c.ru/db/v8327doc/content/{cid}/hdoc"
        html = fetch(url)
        if not html:
            continue

        title = get_title(html)
        title_lower = title.lower()

        is_form_related = any(kw in title_lower for kw in form_keywords)
        if not is_form_related:
            continue

        text = clean(html)
        safe = re.sub(r'[<>:"/\\|?*]', "_", title)[:60]
        fn = f"syntax_{cid}_{safe}.txt"
        (OUT / fn).write_text(
            f"# {title}\n# Content ID: {cid}\n\n{text}", encoding="utf-8"
        )
        results.append({"cid": cid, "title": title, "file": fn, "chars": len(text)})

        if len(results) % 5 == 0:
            print(f"  Found {len(results)} form-related entries...")

        time.sleep(0.3)

    print(f"  Total form-related syntax entries: {len(results)}")
    return results


def scrape_chapter7():
    """Scrape Chapter 7 TI topics"""
    print("Chapter 7 (Forms)...")

    # Get the chapter page to find all TI IDs
    html = fetch("https://its.1c.ru/db/v8327doc/content/52/hdoc")
    if not html:
        print("  FATAL: cannot fetch chapter 7")
        return []

    ti_ids = sorted(set(re.findall(r"TI(\d+)", html)))
    print(f"  Found {len(ti_ids)} TI topics")

    # Save TOC
    (OUT / "chapter7_toc.txt").write_text(clean(html), encoding="utf-8")

    results = []
    for i, ti_id in enumerate(ti_ids, 1):
        r = scrape_ti(ti_id, i, len(ti_ids))
        results.append(r)
        time.sleep(0.5)

    return results


def scrape_appendix():
    """Appendix 11 - element naming rules"""
    print("Appendix 11...")
    html = fetch("https://its.1c.ru/db/v8327doc/content/95/hdoc")
    if html:
        text = clean(html)
        (OUT / "appendix11_naming_rules.txt").write_text(text, encoding="utf-8")
        print(f"  OK ({len(text)}ch)")


def scrape_v85():
    """Check for 8.5 form changes"""
    print("8.5 changes...")
    # Try v851doc database
    for db in ["v851doc", "v85doc"]:
        html = fetch(f"https://its.1c.ru/db/{db}/")
        if html and len(html) > 5000:
            title = get_title(html)
            print(f"  Found {db}: {title}")
            # Try to get Chapter 7 equivalent in 8.5
            html2 = fetch(f"https://its.1c.ru/db/{db}/browse/13/-1")
            if html2:
                cids = re.findall(r'href="/db/{}/content/(\d+)/hdoc"'.format(db), html2)
                text = clean(html2)
                (OUT / f"v85_index.txt").write_text(text, encoding="utf-8")
                print(f"  {db} index: {len(cids)} sections")
            break


def main():
    print("=" * 50)
    print("ITS Forms Scraper v2")
    print("=" * 50)

    if not login():
        print("FATAL: Login failed")
        return

    ch7 = scrape_chapter7()
    syntax = scrape_syntax_helper()
    scrape_appendix()
    scrape_v85()

    # Save manifest
    manifest = {
        "chapter7": ch7,
        "syntax": syntax,
        "stats": {
            "ch7_topics": len(ch7),
            "ch7_chars": sum(r.get("chars", 0) for r in ch7),
            "syntax_entries": len(syntax),
            "syntax_chars": sum(r.get("chars", 0) for r in syntax),
        },
        "scraped_at": time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    (OUT / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    s = manifest["stats"]
    print(
        f"\nDONE: {s['ch7_topics']} topics ({s['ch7_chars']:,}ch) + {s['syntax_entries']} syntax ({s['syntax_chars']:,}ch)"
    )
    print(f"Output: {OUT}")


if __name__ == "__main__":
    main()

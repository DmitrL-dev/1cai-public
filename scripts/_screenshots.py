"""Capture portal screenshots for the README. Backend :8000 + portal :3000 must be up."""
import os
import time

from playwright.sync_api import sync_playwright

OUT = r"C:\1cAI\docs\images"
os.makedirs(OUT, exist_ok=True)
BASE = "http://localhost:3000"

STATIC = [
    ("/quality", "quality"),
    ("/metadata", "metadata"),
    ("/change", "change"),
    ("/architecture", "architecture"),
    ("/testing", "testing"),
    ("/edt-mcp", "edt-mcp"),
    ("/requirements", "requirements"),
    ("/security", "security"),
    ("/", "dashboard"),
]


def shot(page, name):
    fp = os.path.join(OUT, name + ".png")
    page.screenshot(path=fp)
    print(f"  {name}.png  {os.path.getsize(fp):,} bytes")


with sync_playwright() as p:
    browser = p.chromium.launch()
    ctx = browser.new_context(viewport={"width": 1440, "height": 900}, device_scale_factor=1)
    page = ctx.new_page()

    # --- auth via "Dev Mode" (real demo JWT) ---
    page.goto(BASE + "/login", wait_until="domcontentloaded")
    time.sleep(1.5)
    try:
        page.click('button:has-text("Dev Mode")', timeout=8000)
        print("dev login clicked")
    except Exception as e:
        print("dev login click FAILED:", e)
    time.sleep(2)

    # --- static pages ---
    for route, name in STATIC:
        try:
            page.goto(BASE + route, wait_until="domcontentloaded")
            time.sleep(3)  # let TanStack Query fetch + render
            shot(page, name)
        except Exception as e:
            print(f"  {name}: ERROR {e}")

    # --- /quality with an expanded hotspot row (shows the reasons drill-down) ---
    try:
        page.goto(BASE + "/quality", wait_until="domcontentloaded")
        time.sleep(3)
        row = page.query_selector('button:has-text("/Ext/Module.bsl")')
        if row:
            row.click()
            time.sleep(1.2)
            shot(page, "quality-hotspot")
        else:
            print("  quality-hotspot: no row found")
    except Exception as e:
        print(f"  quality-hotspot: ERROR {e}")

    # --- /rentgen with a populated call graph ---
    try:
        page.goto(BASE + "/rentgen", wait_until="domcontentloaded")
        time.sleep(2)
        inp = page.query_selector("input")
        if inp:
            inp.fill("ПроверитьВозможностьВыгрузки")
        try:
            page.click('button:has-text("Analyze")', timeout=5000)
        except Exception:
            page.click('button:has-text("Анализ")', timeout=5000)
        time.sleep(6)  # force-graph render + settle
        shot(page, "rentgen")
    except Exception as e:
        print(f"  rentgen: ERROR {e}")

    browser.close()
print("DONE")

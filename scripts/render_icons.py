"""Rasterize the code-native SVG mark for iOS and PWA. Dev-only Playwright dependency."""
from pathlib import Path
from playwright.sync_api import sync_playwright

static=Path(__file__).resolve().parents[1]/'app/static'
with sync_playwright() as p:
    browser=p.chromium.launch(channel='chrome',headless=True)
    page=browser.new_page(viewport={'width':192,'height':192},device_scale_factor=1)
    page.goto((static/'logo.svg').as_uri())
    for size,name in [(192,'icon-192.png'),(180,'apple-touch-icon.png'),(512,'icon-512.png')]:
        page.set_viewport_size({'width':size,'height':size})
        page.locator('svg').evaluate("(el, size) => { el.setAttribute('width', size); el.setAttribute('height', size); }",size)
        page.screenshot(path=str(static/name),omit_background=True)
    browser.close()

"""Figure 1: the timeline as the dashboard exports it for publication, as an SVG and a PDF (183 mm wide, Arial).

    uv run --group figures python figures/fig1_ecosystem.py [page]

The page is the dashboard built in build/site (fairtox site build/site), or the address given, such as that of the
published dashboard. Needs Google Chrome and Arial.
"""
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

OUT = Path(__file__).with_suffix('.pdf')
SVG = OUT.with_suffix('.svg')

with sync_playwright() as pw:
    browser = pw.chromium.launch(channel='chrome')
    page = browser.new_page()
    page.goto(sys.argv[1] if sys.argv[1:] else Path('build/site/index.html').resolve().as_uri(),
              wait_until='domcontentloaded')
    SVG.write_text(page.evaluate('publicationSVG()'), encoding='utf-8')
    page.goto(SVG.resolve().as_uri())
    height = page.evaluate('document.documentElement.getAttribute("height")')
    page.pdf(path=OUT, width='183mm', height=height, page_ranges='1')
    browser.close()
print(OUT, height)

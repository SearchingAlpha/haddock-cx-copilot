"""Screenshot the running UI at desktop and mobile widths with Playwright.

    python -m scripts.shoot --out .impeccable/review --prefix before
    python -m scripts.shoot --pages / /tickets/T-001 /metrics
"""

import argparse
from pathlib import Path

from playwright.sync_api import sync_playwright

VIEWPORTS = {"desktop": (1440, 900), "mobile": (390, 844)}


def slug(path: str) -> str:
    return path.strip("/").replace("/", "-") or "inbox"


def main() -> None:
    parser = argparse.ArgumentParser(prog="scripts.shoot")
    parser.add_argument("--base", default="http://localhost:8000")
    parser.add_argument("--pages", nargs="+", default=["/", "/tickets/T-001", "/metrics"])
    parser.add_argument("--out", default=".impeccable/review")
    parser.add_argument("--prefix", default="")
    args = parser.parse_args()

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch()
        for name, (w, h) in VIEWPORTS.items():
            page = browser.new_page(viewport={"width": w, "height": h}, device_scale_factor=1)
            for path in args.pages:
                page.goto(args.base + path, wait_until="networkidle")
                page.wait_for_timeout(400)  # let fonts and HTMX settle
                file = out / f"{args.prefix + '-' if args.prefix else ''}{slug(path)}-{name}.png"
                page.screenshot(path=str(file), full_page=True)
                print(file)
            page.close()
        browser.close()


if __name__ == "__main__":
    main()

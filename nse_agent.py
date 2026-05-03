#!/usr/bin/env python3
"""
NSE Smart Money Agent — Fully automated, zero-touch.
Downloads 1Y CSVs from NSE using browser automation, then emails the heatmap.
"""

import os, sys, time, shutil
from pathlib import Path
from datetime import datetime

SCRIPT_DIR   = Path(__file__).parent
DOWNLOAD_DIR = SCRIPT_DIR / "downloads"
DOWNLOAD_DIR.mkdir(exist_ok=True)


def download_nse_csvs():
    from playwright.sync_api import sync_playwright

    print("\nStarting browser...")

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=False,   # visible browser avoids HTTP2 issues
            args=["--no-sandbox", "--disable-blink-features=AutomationControlled"]
        )
        context = browser.new_context(
            accept_downloads=True,
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/124.0.0.0 Safari/537.36",
            viewport={"width": 1280, "height": 800}
        )
        page = context.new_page()

        # Step 1: Hit homepage first to get cookies
        print("  Loading NSE homepage...")
        try:
            page.goto("https://www.nseindia.com", timeout=30000, wait_until="domcontentloaded")
            time.sleep(3)
        except Exception as e:
            print(f"  [warn] Homepage: {e}")

        # Step 2: Navigate to deals page
        print("  Navigating to bulk/block deals...")
        try:
            page.goto("https://www.nseindia.com/report-detail/display-bulk-and-block-deals",
                      timeout=30000, wait_until="domcontentloaded")
            time.sleep(4)
        except Exception as e:
            print(f"  [warn] Deals page: {e}")
            # Try clicking through menu instead
            try:
                page.goto("https://www.nseindia.com", timeout=20000, wait_until="domcontentloaded")
                time.sleep(2)
                page.click("text=Market Data")
                time.sleep(1)
                page.click("text=Bulk Deals")
                time.sleep(3)
            except Exception as e2:
                print(f"  [warn] Menu nav: {e2}")

        print(f"  Current URL: {page.url}")

        bulk_path  = None
        block_path = None

        for deal_type, label, file_name in [
            ("Bulk Deals",  "bulk",  "bulk_1y.csv"),
            ("Block Deals", "block", "block_1y.csv"),
        ]:
            print(f"\n  Downloading {deal_type} (1Y)...")
            try:
                # Select deal type from dropdown
                dropdown = page.locator("select").first
                dropdown.select_option(label=deal_type)
                time.sleep(2)
            except Exception as e:
                print(f"  [warn] Dropdown: {e}")

            try:
                # Click 1Y button
                page.locator("button:has-text('1Y'), span:has-text('1Y')").first.click()
                time.sleep(3)
            except Exception as e:
                print(f"  [warn] 1Y button: {e}")

            try:
                # Click download
                with page.expect_download(timeout=30000) as dl_info:
                    page.locator("a:has-text('Download'), button:has-text('Download (.csv)')").first.click()
                download = dl_info.value
                save_path = str(DOWNLOAD_DIR / file_name)
                download.save_as(save_path)
                size = Path(save_path).stat().st_size // 1024
                print(f"  ✅ {file_name}: {size}KB")
                if label == "bulk":
                    bulk_path = save_path
                else:
                    block_path = save_path
            except Exception as e:
                print(f"  [warn] Download failed: {e}")

        browser.close()

    return bulk_path, block_path


def copy_to_script_dir(bulk_path, block_path):
    copied = 0
    for path, name in [(bulk_path, "bulk_1y.csv"), (block_path, "block_1y.csv")]:
        if path and Path(path).exists() and Path(path).stat().st_size > 1000:
            dest = SCRIPT_DIR / name
            shutil.copy2(path, dest)
            rows = sum(1 for _ in open(dest)) - 1
            print(f"  {name}: {rows} rows")
            copied += 1
        else:
            print(f"  ⚠️  {name} not updated — keeping existing")
    return copied


def run_report():
    script = SCRIPT_DIR / "nse_daily.py"
    if not script.exists():
        print(f"  ❌ nse_daily.py not found")
        return False
    print("\nRunning report...")
    import subprocess
    result = subprocess.run(
        [sys.executable, str(script)],
        env=os.environ.copy(),
        cwd=str(SCRIPT_DIR)
    )
    return result.returncode == 0


def main():
    today = datetime.today().strftime("%d %b %Y")
    print(f"\n⚡ NSE Smart Money Agent — {today}")
    print("=" * 45)

    bulk_existing = SCRIPT_DIR / "bulk_1y.csv"
    needs_download = True

    if bulk_existing.exists():
        age_hours = (time.time() - bulk_existing.stat().st_mtime) / 3600
        if age_hours < 20:
            print(f"\nCSVs fresh ({age_hours:.0f}h old) — skipping download")
            needs_download = False
        else:
            print(f"\nCSVs are {age_hours:.0f}h old — downloading fresh data")

    if needs_download:
        print("\nStep 1: Downloading CSVs from NSE...")
        bulk_path, block_path = download_nse_csvs()

        print("\nStep 2: Updating files...")
        copied = copy_to_script_dir(bulk_path, block_path)
        if copied == 0:
            print("  ⚠️  Using existing CSVs")
            if not bulk_existing.exists():
                print("  ❌ No CSVs found. Download manually from NSE website.")
                sys.exit(1)

    print("\nStep 3: Generating report...")
    success = run_report()

    if success:
        print("\n✅ Done! Check your email.")
    else:
        print("\n❌ Report failed.")
        sys.exit(1)


if __name__ == "__main__":
    main()

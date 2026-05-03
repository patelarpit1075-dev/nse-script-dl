#!/usr/bin/env python3
"""
NSE Smart Money Agent

Fully automated - no manual steps needed.
Runs Playwright to download fresh 1Y CSVs from NSE, then generates report.

Setup (one time):
  pip3 install playwright pandas requests numpy
  playwright install chromium

Run:
  bash ~/nse-smart-money/run_agent.sh

Or manually:
  cd ~/nse-smart-money
  NSE_EMAIL_FROM=... NSE_EMAIL_TO=... NSE_EMAIL_PASSWORD=... python3 nse_agent.py
"""

import os, sys, time, shutil
from pathlib import Path
from datetime import datetime

SCRIPT_DIR = Path(__file__).parent
DOWNLOAD_DIR = SCRIPT_DIR / "downloads"
DOWNLOAD_DIR.mkdir(exist_ok=True)


def download_nse_csvs():
    """Use Playwright to download 1Y Bulk and Block deal CSVs from NSE."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("Installing Playwright...")
        os.system("pip3 install playwright --break-system-packages -q")
        os.system("playwright install chromium")
        from playwright.sync_api import sync_playwright

    print("\nStarting browser to download NSE data...")

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-setuid-sandbox"]
        )
        context = browser.new_context(
            accept_downloads=True,
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/124.0.0.0 Safari/537.36"
        )
        page = context.new_page()

        # Go to NSE bulk/block deals page
        print("  Opening NSE website...")
        page.goto("https://www.nseindia.com/report-detail/display-bulk-and-block-deals", timeout=30000)
        page.wait_for_load_state("networkidle", timeout=20000)
        time.sleep(3)

        bulk_path = None
        block_path = None

        # ── Download BULK deals ──────────────────────────────────────────────
        print("  Downloading Bulk Deals (1Y)...")
        try:
            # Select Bulk Deals from dropdown
            page.select_option("select[name='selectOption'], #selectOption, select", label="Bulk Deals")
            time.sleep(1)
        except:
            pass  # Already on bulk deals

        try:
            # Click 1Y button
            page.click("text=1Y")
            time.sleep(2)
        except Exception as e:
            print(f"  [warn] 1Y button: {e}")

        try:
            # Click download button and capture file
            with page.expect_download(timeout=30000) as dl:
                page.click("text=Download (.csv), a[href*='.csv'], button:has-text('Download')")
            download = dl.value
            bulk_path = str(DOWNLOAD_DIR / "bulk_1y.csv")
            download.save_as(bulk_path)
            size = Path(bulk_path).stat().st_size // 1024
            print(f"  Bulk CSV downloaded: {size}KB")
        except Exception as e:
            print(f"  [warn] Bulk download failed: {e}")
            bulk_path = None

        time.sleep(2)

        # ── Download BLOCK deals ─────────────────────────────────────────────
        print("  Downloading Block Deals (1Y)...")
        try:
            page.select_option("select[name='selectOption'], #selectOption, select", label="Block Deals")
            time.sleep(2)
            page.click("text=1Y")
            time.sleep(2)
        except Exception as e:
            print(f"  [warn] Block select: {e}")

        try:
            with page.expect_download(timeout=30000) as dl:
                page.click("text=Download (.csv), a[href*='.csv'], button:has-text('Download')")
            download = dl.value
            block_path = str(DOWNLOAD_DIR / "block_1y.csv")
            download.save_as(block_path)
            size = Path(block_path).stat().st_size // 1024
            print(f"  Block CSV downloaded: {size}KB")
        except Exception as e:
            print(f"  [warn] Block download failed: {e}")
            block_path = None

        browser.close()

    return bulk_path, block_path


def fallback_api_download():
    """
    Fallback: use requests with proper session to download CSVs.
    Works when Playwright download buttons are hard to click.
    """
    import requests
    from datetime import timedelta

    today = datetime.today()
    one_year_ago = today - timedelta(days=366)
    frm = one_year_ago.strftime("%d-%m-%Y")
    to  = today.strftime("%d-%m-%Y")

    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/124.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Referer": "https://www.nseindia.com/",
    }

    session = requests.Session()
    session.headers.update(headers)

    print("  Warming up NSE session...")
    try:
        session.get("https://www.nseindia.com", timeout=15)
        time.sleep(2)
        session.get("https://www.nseindia.com/report-detail/display-bulk-and-block-deals", timeout=15)
        time.sleep(2)
    except Exception as e:
        print(f"  [warn] Session warm: {e}")

    results = {}
    for deal_type, label in [("bulk-deals", "bulk"), ("block-deals", "block")]:
        url = f"https://www.nseindia.com/api/historical/{deal_type}?from={frm}&to={to}&csv=true"
        print(f"  Trying {label} CSV download...")
        try:
            r = session.get(url, timeout=60)
            print(f"  {label}: status={r.status_code}, size={len(r.content)}")
            if r.status_code == 200 and len(r.content) > 1000:
                path = str(DOWNLOAD_DIR / f"{label}_1y.csv")
                with open(path, "wb") as f:
                    f.write(r.content)
                print(f"  {label} saved: {len(r.content)//1024}KB")
                results[label] = path
            else:
                results[label] = None
        except Exception as e:
            print(f"  {label} failed: {e}")
            results[label] = None
        time.sleep(2)

    return results.get("bulk"), results.get("block")


def copy_to_script_dir(bulk_path, block_path):
    """Copy downloaded CSVs to the script directory."""
    copied = 0
    if bulk_path and Path(bulk_path).exists() and Path(bulk_path).stat().st_size > 1000:
        dest = SCRIPT_DIR / "bulk_1y.csv"
        shutil.copy2(bulk_path, dest)
        rows = sum(1 for _ in open(dest))
        print(f"  bulk_1y.csv: {rows} rows")
        copied += 1
    else:
        print("  ⚠️  bulk_1y.csv not updated — keeping existing file")

    if block_path and Path(block_path).exists() and Path(block_path).stat().st_size > 100:
        dest = SCRIPT_DIR / "block_1y.csv"
        shutil.copy2(block_path, dest)
        rows = sum(1 for _ in open(dest))
        print(f"  block_1y.csv: {rows} rows")
        copied += 1
    else:
        print("  ⚠️  block_1y.csv not updated — keeping existing file")

    return copied


def run_report():
    """Run the main nse_daily.py report script."""
    script = SCRIPT_DIR / "nse_daily.py"
    if not script.exists():
        print(f"  ❌ nse_daily.py not found at {script}")
        return False

    print("\nRunning report...")
    import subprocess
    env = os.environ.copy()
    result = subprocess.run(
        [sys.executable, str(script)],
        env=env,
        cwd=str(SCRIPT_DIR)
    )
    return result.returncode == 0


def main():
    today = datetime.today().strftime("%d %b %Y")
    print(f"\n⚡ NSE Smart Money Agent — {today}")
    print("=" * 45)

    # Check if existing CSVs are recent enough (less than 2 days old)
    bulk_existing = SCRIPT_DIR / "bulk_1y.csv"
    needs_download = True

    if bulk_existing.exists():
        age_hours = (time.time() - bulk_existing.stat().st_mtime) / 3600
        if age_hours < 20:  # Less than 20 hours old
            print(f"\nCSVs are fresh ({age_hours:.0f}h old) — skipping download")
            needs_download = False
        else:
            print(f"\nCSVs are {age_hours:.0f}h old — downloading fresh data")

    if needs_download:
        print("\nStep 1: Download fresh CSVs from NSE")

        # Try Playwright first
        bulk_path, block_path = download_nse_csvs()

        # If Playwright failed, try API fallback
        if not bulk_path:
            print("  Playwright failed — trying API fallback...")
            bulk_path, block_path = fallback_api_download()

        # Copy to script dir
        print("\nStep 2: Updating CSV files")
        copied = copy_to_script_dir(bulk_path, block_path)

        if copied == 0:
            print("  ⚠️  No new CSVs downloaded — using existing files")
            if not bulk_existing.exists():
                print("  ❌ No existing CSVs either. Please download manually from:")
                print("     https://nseindia.com/report-detail/display-bulk-and-block-deals")
                sys.exit(1)

    # Run the report
    print("\nStep 3: Generate and email report")
    success = run_report()

    if success:
        print("\n✅ Agent complete! Check your email.")
    else:
        print("\n❌ Report failed. Check logs.")
        sys.exit(1)


if __name__ == "__main__":
    main()

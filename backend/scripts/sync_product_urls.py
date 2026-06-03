"""
sync_product_urls.py — Verify and add product URLs to knowledge base files.

Fetches the Shopify sitemap from www.boomschors.nl and matches product URLs
to knowledge base .txt files. Shows a diff of missing or outdated ## Link:
fields. Use --apply to write changes to disk.

Usage:
    python backend/scripts/sync_product_urls.py
    python backend/scripts/sync_product_urls.py --apply
"""

import argparse
import re
import sys
import xml.etree.ElementTree as ET
from difflib import SequenceMatcher
from pathlib import Path

try:
    import requests
except ImportError:
    print("ERROR: 'requests' not installed. Run: pip install requests")
    sys.exit(1)

INDEX_SITEMAP_URL = "https://www.boomschors.nl/sitemap.xml"
KB_DIR = Path(__file__).parent.parent / "knowledge_base"
LINK_PATTERN = re.compile(r"^## Link:\s*(.+)$", re.MULTILINE)


def fetch_product_urls():
    """Fetch all product URLs from the Shopify sitemap index."""
    ns = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}

    print(f"Fetching sitemap index: {INDEX_SITEMAP_URL}")
    try:
        resp = requests.get(INDEX_SITEMAP_URL, timeout=15)
        resp.raise_for_status()
    except requests.RequestException as e:
        print(f"ERROR: Could not fetch sitemap index: {e}")
        sys.exit(1)

    root = ET.fromstring(resp.content)
    product_sitemaps = [
        loc.text.strip()
        for loc in root.findall(".//sm:loc", ns)
        if loc.text and "sitemap_products" in loc.text
    ]

    if not product_sitemaps:
        print("ERROR: No product sitemap found in sitemap index.")
        sys.exit(1)

    all_urls = []
    for sitemap_url in product_sitemaps:
        print(f"Fetching product sitemap: {sitemap_url}")
        try:
            r = requests.get(sitemap_url, timeout=15)
            r.raise_for_status()
        except requests.RequestException as e:
            print(f"  WARNING: Could not fetch {sitemap_url}: {e}")
            continue
        sub_root = ET.fromstring(r.content)
        urls = [loc.text.strip() for loc in sub_root.findall(".//sm:loc", ns) if loc.text]
        all_urls.extend(urls)

    print(f"Found {len(all_urls)} product URLs total.")
    return all_urls


def slug_from_url(url):
    """Extract the product slug from a Shopify URL (strip query params)."""
    path = url.split("?")[0].rstrip("/")
    return path.split("/")[-1]


def similarity(a, b):
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()


def best_url_match(product_name, urls):
    """Find the best matching URL for a given product name."""
    name_slug = product_name.lower().replace(" ", "-").replace("(", "").replace(")", "")
    best_score = 0
    best_url = None
    for url in urls:
        slug = slug_from_url(url)
        score = similarity(name_slug, slug)
        if score > best_score:
            best_score = score
            best_url = url
    return best_url, best_score


def extract_product_name(content):
    """Extract product name from the first line: '# PRODUCT: <name>'"""
    match = re.match(r"^# PRODUCT:\s*(.+)$", content, re.MULTILINE)
    return match.group(1).strip() if match else None


def process_files(urls, apply=False):
    txt_files = sorted(KB_DIR.glob("*.txt"))
    product_files = []
    for f in txt_files:
        content = f.read_text(encoding="utf-8")
        if content.startswith("# PRODUCT:"):
            product_files.append(f)

    print(f"\nChecking {len(product_files)} product files...\n")

    changes = []

    for f in product_files:
        content = f.read_text(encoding="utf-8")
        product_name = extract_product_name(content)
        if not product_name:
            continue

        existing_link = LINK_PATTERN.search(content)
        existing_url = existing_link.group(1).strip() if existing_link else None

        best_url, score = best_url_match(product_name, urls)

        if existing_url:
            # Clean existing URL (strip query params) vs best match (also stripped)
            existing_clean = existing_url.split("?")[0].rstrip("/")
            best_clean = best_url.split("?")[0].rstrip("/") if best_url else None
            if existing_clean == best_clean or score < 0.5:
                print(f"  OK  {f.name}")
                continue
            status = "UPDATE"
        else:
            if score < 0.4:
                print(f"  SKIP {f.name} — no match found (best score: {score:.2f})")
                continue
            status = "ADD"

        print(f"  {status} {f.name}")
        print(f"       Product : {product_name}")
        if existing_url:
            print(f"       Current : {existing_url}")
        print(f"       Proposed: {best_url}  (score: {score:.2f})")

        changes.append((f, content, existing_link, best_url, status))

    if not changes:
        print("\nAll product files are up to date.")
        return

    print(f"\n{len(changes)} file(s) need changes.")

    if not apply:
        print("\nRun with --apply to write these changes to disk.")
        return

    for f, content, existing_link, new_url, status in changes:
        if status == "UPDATE" and existing_link:
            new_content = content[:existing_link.start()] + f"## Link: {new_url}" + content[existing_link.end():]
        elif status == "ADD":
            # Insert ## Link: after ## Categorie block
            cat_match = re.search(r"(## Categorie\n.+?\n)", content, re.DOTALL)
            if cat_match:
                insert_pos = cat_match.end()
                new_content = content[:insert_pos] + f"\n## Link: {new_url}\n" + content[insert_pos:]
            else:
                # Fallback: insert after first line
                first_newline = content.index("\n") + 1
                new_content = content[:first_newline] + f"\n## Link: {new_url}\n" + content[first_newline:]
        else:
            continue

        f.write_text(new_content, encoding="utf-8")
        print(f"  WRITTEN: {f.name}")

    print(f"\nDone. {len(changes)} file(s) updated.")
    print("Re-ingest the knowledge base: POST /api/ingest with X-Admin-Key header.")


def main():
    parser = argparse.ArgumentParser(description="Sync product URLs from Shopify sitemap to knowledge base.")
    parser.add_argument("--apply", action="store_true", help="Write changes to disk (default: dry run)")
    args = parser.parse_args()

    urls = fetch_product_urls()
    process_files(urls, apply=args.apply)


if __name__ == "__main__":
    main()

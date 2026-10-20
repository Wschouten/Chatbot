"""Mirror the public Shopify product feed into the knowledge base.

boomschors.nl exposes /products.json without a token: title, description and, per
variant, price and availability. Each product becomes knowledge_base/shop_<handle>.txt,
so ingest_documents() embeds it like any other KB file and its content hash re-embeds
only products whose text actually changed.
"""
import glob
import html
import logging
import os
import re

import requests

logger = logging.getLogger(__name__)

SHOP_URL = os.getenv("SHOPIFY_PUBLIC_URL", "https://www.boomschors.nl").rstrip("/")
PREFIX = "shop_"


def _plain(body_html: str) -> str:
    text = re.sub(r"<\s*(br|/p|/li|/h\d)\s*/?>", "\n", body_html or "", flags=re.I)
    text = html.unescape(re.sub(r"<[^>]+>", " ", text))
    lines = (re.sub(r"[ \t ]+", " ", line).strip() for line in text.splitlines())
    return "\n".join(line for line in lines if line)


def _euro(price: str) -> str:
    return "€ " + f"{float(price):.2f}".replace(".", ",")


def render_product(product: dict) -> str:
    # No date or timestamp in here: it would change the content hash every refresh
    # and re-embed the whole catalogue each day.
    variants = "\n".join(
        f"- {v['title']}: {_euro(v['price'])} — "
        + ("leverbaar" if v.get("available") else "nu niet leverbaar")
        for v in product.get("variants", [])
    )
    return (
        f"# PRODUCT: {product['title']} (webshop)\n"
        f"## Link: {SHOP_URL}/products/{product['handle']}\n"
        f"## Varianten en prijzen\n{variants}\n"
        f"## Omschrijving\n{_plain(product.get('body_html'))}\n"
    )


def refresh_catalog(kb_path: str = "./knowledge_base") -> str:
    """Write one KB file per webshop product; on a feed error, leave the old files alone."""
    try:
        # ponytail: one page of 250 — the shop has ~95 products; page when it passes 250.
        resp = requests.get(f"{SHOP_URL}/products.json", params={"limit": 250}, timeout=15)
        resp.raise_for_status()
        products = resp.json()["products"]
    except (requests.RequestException, ValueError, KeyError) as e:
        logger.warning("Shopify catalogue refresh failed, keeping existing files: %s", e)
        return "Shopify catalogue: refresh failed"
    if not products:
        logger.warning("Shopify catalogue feed was empty, keeping existing files")
        return "Shopify catalogue: empty feed"

    wanted = set()
    for product in products:
        path = os.path.join(kb_path, f"{PREFIX}{product['handle']}.txt")
        wanted.add(os.path.abspath(path))
        with open(path, "w", encoding="utf-8") as f:
            f.write(render_product(product))

    for path in glob.glob(os.path.join(kb_path, f"{PREFIX}*.txt")):
        if os.path.abspath(path) not in wanted:
            os.remove(path)
    return f"Shopify catalogue: {len(products)} products written"

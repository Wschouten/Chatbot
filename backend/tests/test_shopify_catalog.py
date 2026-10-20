"""Webshop feed → knowledge-base files (shopify_catalog.py).

The public /products.json feed is mirrored into knowledge_base/shop_<handle>.txt so the
bot can name current prices and availability. requests.get is mocked: the suite never
calls the shop.
"""
import os
import sys

import requests

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import shopify_catalog  # noqa: E402

PRODUCT = {
    "title": "Franse Boomschors 20-45mm",
    "handle": "franse-boomschors-20-45",
    "body_html": "<p>Mooie schors &amp; <strong>duurzaam</strong>.</p><ul><li>Fractie 20-45 mm</li></ul>",
    "variants": [
        {"title": "1 zak (40 liter)", "price": "22.95", "available": True},
        {"title": "Big Bale", "price": "399.95", "available": False},
    ],
}


class _Resp:
    def __init__(self, products):
        self._products = products

    def raise_for_status(self):
        pass

    def json(self):
        return {"products": self._products}


def test_render_product_has_link_prices_and_availability():
    text = shopify_catalog.render_product(PRODUCT)
    assert text.startswith("# PRODUCT: Franse Boomschors 20-45mm (webshop)\n")
    assert "## Link: https://www.boomschors.nl/products/franse-boomschors-20-45" in text
    assert "- 1 zak (40 liter): € 22,95 — leverbaar" in text
    assert "- Big Bale: € 399,95 — nu niet leverbaar" in text
    assert "Mooie schors & duurzaam ." in text
    assert "Fractie 20-45 mm" in text
    assert "<" not in text


def test_refresh_writes_new_and_removes_vanished_products(tmp_path, monkeypatch):
    (tmp_path / "shop_old-product.txt").write_text("weg", encoding="utf-8")
    (tmp_path / "Boomschors.txt").write_text("handgeschreven", encoding="utf-8")
    monkeypatch.setattr(shopify_catalog.requests, "get", lambda *a, **k: _Resp([PRODUCT]))

    shopify_catalog.refresh_catalog(str(tmp_path))

    assert sorted(p.name for p in tmp_path.iterdir()) == ["Boomschors.txt", "shop_franse-boomschors-20-45.txt"]


def test_failed_feed_keeps_existing_files(tmp_path, monkeypatch):
    (tmp_path / "shop_keep.txt").write_text("blijft", encoding="utf-8")

    def boom(*a, **k):
        raise requests.ConnectionError("down")

    monkeypatch.setattr(shopify_catalog.requests, "get", boom)
    shopify_catalog.refresh_catalog(str(tmp_path))
    monkeypatch.setattr(shopify_catalog.requests, "get", lambda *a, **k: _Resp([]))
    shopify_catalog.refresh_catalog(str(tmp_path))

    assert (tmp_path / "shop_keep.txt").read_text(encoding="utf-8") == "blijft"

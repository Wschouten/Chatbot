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
from rag_engine import RagEngine  # noqa: E402

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


class _RankedCollection:
    """Chroma stand-in: chunks in a fixed nearest-first order; honours where $in/$nin."""

    def __init__(self, sources):
        self.ids = [f"{s}_chunk_0" for s in sources]

    def query(self, query_embeddings, n_results, where=None):
        ids = self.ids
        if where:
            cond = where["source"]
            keep = (lambda s: s in cond["$in"]) if "$in" in cond else (lambda s: s not in cond["$nin"])
            ids = [i for i in ids if keep(i.rsplit("_chunk_", 1)[0])]
        ids = ids[:n_results]
        return {"ids": [ids], "documents": [ids], "distances": [[0.5] * len(ids)]}


def test_webshop_pages_cannot_crowd_out_the_hand_written_kb(tmp_path):
    # RAG evaluation 2026-10-20: in a single pass, tuinaarde product pages filled the
    # top results and the FAQ's PFAS answer never reached the model.
    shop = [f"shop_tuinaarde-{n}.txt" for n in range(12)]
    kb = ["Tuinaarde (Algemeen).txt", "FAQ GCG.txt"]
    for name in shop + kb:
        (tmp_path / name).write_text("x", encoding="utf-8")
    engine = object.__new__(RagEngine)
    engine.knowledge_base_path = str(tmp_path)
    engine.relevance_threshold = 1.2
    engine.collection = _RankedCollection(shop + kb)  # every shop page ranks above the KB

    context = engine._retrieve_context([0.0])

    assert "FAQ GCG.txt_chunk_0" in context
    assert context.startswith("Tuinaarde (Algemeen).txt_chunk_0")
    assert sum(part.startswith("shop_") for part in context.split("\n\n")) == 3

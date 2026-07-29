"""Knowledge-base re-indexing on content change.

Ingestion used to skip any file whose `<file>_chunk_0` id already existed, so an
*edited* file was never re-indexed. Because chroma_db lives on the Railway volume,
the stale answer survived every deploy — that is why the "kooiaap" question was
answered wrong in production while the corrected text sat in FAQ GCG.txt.

These tests drive ingest_documents() against a fake Chroma collection, so they run
offline with no API keys.
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import rag_engine as rag_engine_module  # noqa: E402
from rag_engine import RagEngine  # noqa: E402


@pytest.fixture(autouse=True)
def _pretend_rag_deps_available(monkeypatch):
    """ingest_documents() bails out early when the optional RAG deps are missing.
    The fake collection stands in for them, so force the flag on."""
    monkeypatch.setattr(rag_engine_module, "RAG_DEPENDENCIES_LOADED", True)


class FakeCollection:
    """Minimal stand-in for a Chroma collection."""

    def __init__(self):
        self.docs: dict[str, dict] = {}  # id -> {"document", "metadata"}
        self.deleted_sources: list[str] = []

    def count(self) -> int:
        return len(self.docs)

    def get(self, limit=None, include=None):
        ids = list(self.docs)
        return {
            "ids": ids,
            "metadatas": [self.docs[i]["metadata"] for i in ids],
            "documents": [self.docs[i]["document"] for i in ids],
        }

    def add(self, documents, embeddings, metadatas, ids):
        for doc, metadata, doc_id in zip(documents, metadatas, ids):
            self.docs[doc_id] = {"document": doc, "metadata": metadata}

    def delete(self, where):
        source = where["source"]
        self.deleted_sources.append(source)
        for doc_id in [i for i, d in self.docs.items() if d["metadata"].get("source") == source]:
            del self.docs[doc_id]


def _engine(kb_dir) -> RagEngine:
    """A RagEngine with just enough wired up to run ingest_documents()."""
    engine = object.__new__(RagEngine)
    engine.knowledge_base_path = str(kb_dir)
    engine.collection = FakeCollection()
    engine._get_embedding = lambda text: [0.0, 0.0, 0.0]  # no OpenAI call
    return engine


def _write(kb_dir, name: str, text: str) -> None:
    (kb_dir / name).write_text(text, encoding="utf-8")


def test_new_file_is_ingested(tmp_path):
    _write(tmp_path, "kooiaap.txt", "Levering met een kooiaap kost 100 euro extra.")
    engine = _engine(tmp_path)

    result = engine.ingest_documents()

    assert "1 new documents processed" in result
    assert engine.collection.count() == 1


def test_unchanged_file_is_skipped(tmp_path):
    _write(tmp_path, "kooiaap.txt", "Levering met een kooiaap kost 100 euro extra.")
    engine = _engine(tmp_path)
    engine.ingest_documents()

    result = engine.ingest_documents()

    assert "1 skipped" in result
    assert engine.collection.deleted_sources == [], "Unchanged file must not be re-embedded"


def test_edited_file_is_reindexed(tmp_path):
    """The core regression: editing a KB file must replace its chunks."""
    _write(tmp_path, "kooiaap.txt", "Levering met een kooiaap is niet mogelijk.")
    engine = _engine(tmp_path)
    engine.ingest_documents()

    _write(tmp_path, "kooiaap.txt", "Levering met een kooiaap kost 100 euro extra.")
    result = engine.ingest_documents()

    assert "1 re-indexed after changes" in result
    assert engine.collection.deleted_sources == ["kooiaap.txt"], (
        "Old chunks must be dropped so the stale answer cannot be retrieved"
    )
    stored = [d["document"] for d in engine.collection.docs.values()]
    assert any("100 euro extra" in doc for doc in stored)
    assert not any("niet mogelijk" in doc for doc in stored), (
        "The superseded text must be gone from the index"
    )


def test_file_indexed_before_hashing_is_refreshed_once(tmp_path):
    """Chunks already on the Railway volume carry no content_hash — treat as changed."""
    _write(tmp_path, "kooiaap.txt", "Levering met een kooiaap kost 100 euro extra.")
    engine = _engine(tmp_path)
    engine.collection.docs["kooiaap.txt_chunk_0"] = {
        "document": "oude tekst",
        "metadata": {"source": "kooiaap.txt", "chunk": "0"},  # no content_hash
    }

    result = engine.ingest_documents()

    assert "1 re-indexed after changes" in result
    assert engine.collection.deleted_sources == ["kooiaap.txt"]


def test_deleted_file_is_cleaned_up(tmp_path):
    _write(tmp_path, "kooiaap.txt", "Levering met een kooiaap kost 100 euro extra.")
    engine = _engine(tmp_path)
    engine.ingest_documents()

    os.remove(tmp_path / "kooiaap.txt")
    result = engine.ingest_documents()

    assert "1 stale sources removed" in result
    assert engine.collection.count() == 0

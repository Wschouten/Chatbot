# Feature 26: Python 3.14 ChromaDB Compatibility Fix

**Track:** Bug Fix
**Effort:** 5 min
**Status:** Done
**Dependencies:** None

## Context

ChromaDB crashes on Python 3.14 because its Pydantic v1 dependency is incompatible. The error is a `pydantic.v1.errors.ConfigError` (not an `ImportError`), so the existing try/except in `rag_engine.py` doesn't catch it and the app crashes on startup.

Error: `ConfigError: unable to infer type for attribute "chroma_server_nofile"`

## Problem

`backend/rag_engine.py` line 18 catches only `ImportError`:

```python
try:
    import chromadb
    from pypdf import PdfReader
    RAG_DEPENDENCIES_LOADED = True
except ImportError as e:
    ...
```

On Python 3.14, ChromaDB partially imports before failing with `ConfigError`, which slips through.

## Solution

### Code Change

In `backend/rag_engine.py` (line 18), broaden the except clause:

```python
except Exception as e:
```

This allows the web app to gracefully degrade to memory mode on Python 3.14 (no vector search, but no crash).

### Running the Evaluation

The evaluation (`python evaluate_rag.py`) requires a working ChromaDB, which means **Python 3.12 or 3.13**. Python 3.14 will not work for evaluation even with the code fix above.

To run the evaluation:

```powershell
# Install Python 3.12 from https://www.python.org/downloads/
cd backend
py -3.12 -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
python evaluate_rag.py
```

## Verification

1. On Python 3.14: `python -c "from rag_engine import RagEngine"` should succeed without error
2. On Python 3.12 venv: `python evaluate_rag.py` should run all 45 test cases and generate reports

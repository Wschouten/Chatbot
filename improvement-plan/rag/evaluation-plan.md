# RAG Quality Improvement Plan

Improving answer quality is the highest-impact work for making this chatbot successful. This plan follows a measure-first approach: build evaluation, establish a baseline, then make changes and prove they help.

---

## 1. Make LLM Model Configurable

**Status:** :black_square_button: Todo
**Effort:** 30 min
**File:** `backend/rag_engine.py`

**Problem:** The string `"gpt-5.2"` is hardcoded in 5 locations. The embedding model `"text-embedding-3-small"` is hardcoded once. Changing models requires editing code in multiple places.

**Changes:**
- Add `self.chat_model` and `self.embedding_model` to `RagEngine.__init__()`, loaded from env vars:
  - `OPENAI_CHAT_MODEL` (default: `gpt-5.2`)
  - `OPENAI_EMBEDDING_MODEL` (default: `text-embedding-3-small`)
- Replace all 5 occurrences of `model="gpt-5.2"` with `model=self.chat_model`
- Replace `model="text-embedding-3-small"` with `model=self.embedding_model`
- Add both env vars to `.env` and `.env.example`

**Important:** Changing the embedding model requires clearing `chroma_db/` and re-ingesting all documents (different vector dimensions). The chat model can be swapped freely.

---

## 2. Build RAG Evaluation Framework

**Status:** :black_square_button: Todo
**Effort:** 2-3 hrs
**Files:** New `backend/evaluation/test_set.json`, New `backend/evaluate_rag.py`

### Test Set Design (~25-30 questions)

**Category 1: Product Information (8-10 questions)**
Example questions:
- "Wat is het verschil tussen Franse boomschors en dennenschors?"
- "Hoe dik moet ik houtsnippers leggen?"
- "Welke kleuren houtsnippers zijn er?"
- "Hoeveel boomschors heb ik nodig voor 70 vierkante meter?" (calculation test)
- "Is schapenwol goed tegen slakken?"
- "Wat zijn hydrokorrels en waarvoor gebruik je ze?"
- "Welke soorten potgrond hebben jullie?"
- "Wat is het verschil tussen Ecolat en Ekoboard?"

**Category 2: FAQ / Policy (5-6 questions)**
- "Hebben jullie kortingscodes?"
- "Wanneer wordt mijn bestelling geleverd?"
- "Kan ik contant betalen?"
- "Is jullie tuinaarde PFAS-vrij?"
- "Kan ik mijn bestelling retourneren?"

**Category 3: Cross-product Recommendations (4-5 questions)**
- "Ik wil onkruid tegengaan in mijn border, wat raden jullie aan?"
- "Welke borderrand past bij mijn tuin?"
- "Wat is beter: boomschors of houtsnippers?"

**Category 4: Out-of-scope / Hallucination Checks (3-4 questions)**
- "Verkopen jullie ook meststoffen?" (not in KB — should return `__UNKNOWN__`)
- "Wat is de prijs van boomschors?" (no pricing in KB)
- "Kunnen jullie mijn tuin ontwerpen?" (out of scope)

**Category 5: English Queries (2-3 questions)**
- "What types of bark mulch do you sell?"
- "How do I install border edging?"

### Test Case Format
```json
{
  "question": "Hoe dik moet ik houtsnippers leggen?",
  "expected_answer_keywords": ["5 cm", "8", "10", "laagdikte"],
  "category": "product_info",
  "expect_unknown": false
}
```

### Evaluation Script Design

The `evaluate_rag.py` script will:

1. **Keyword matching** — Check if expected terms appear in the answer (case-insensitive). Score = hits / total expected keywords.
2. **LLM-as-judge** — Use the same OpenAI client to rate semantic accuracy on a 1-5 scale with a brief explanation.
3. **Hallucination detection** — For `expect_unknown: true` questions, verify the answer contains `__UNKNOWN__`.
4. **Latency tracking** — Measure response time per question.
5. **Category breakdown** — Pass rate and average latency per category.

**Output:**
- `backend/evaluation/evaluation_report.md` — Human-readable report with tables
- `backend/evaluation/evaluation_results.json` — Machine-readable for tracking over time

---

## 3. Add Metadata to Knowledge Base Chunks

**Status:** :black_square_button: Todo
**Effort:** 2-3 hrs
**File:** `backend/rag_engine.py`

**Problem:** Currently chunks only store `{"source": filename, "chunk": index}` as metadata. The knowledge base files have rich structure that's being thrown away.

**Changes:**

Add `_extract_metadata_from_content()` that parses markdown headers:
- `doc_type`: "product" (from `# PRODUCT:`) or "knowledge" (from `# KENNIS:`)
- `product_name` or `topic`: text after the header prefix
- `category`: extracted from the `## Categorie` section (e.g., "Kantopsluiting / Borderrand")

Modify `_ingest_text_chunks()` to accept a `file_metadata` dict and merge it into each chunk's ChromaDB metadata.

Update `ingest_documents()` to call the extractor before chunking.

**Knowledge base categories discovered:**

| Category | Files | Count |
|---|---|---|
| Bodembedekking (ground cover) | Boomschors, Houtsnippers, Houtmulch, Bio Hempcover, Bio Sheep Wool, Anti-worteldoek | 6 |
| Potgrond / Tuinaarde (soil) | Various potgrond and tuinaarde files | 10 |
| Kantopsluiting (edging) | Ecolat, Ekoboard, Recy-Edge, Ecopic, Massieve Paaltje | 6 |
| Haardhout / Aanmaak (firewood) | Haardhout Eiken, Aanmaakhout, Aanmaakkrullen | 3 |
| Accessoires | Gronddoekpennen, Hydrokorrels | 2 |
| Overig | Tuin Stapstenen, Speelmix, Florentus Topstart | 3 |
| FAQ/Kennis | FAQ GCG, general guides | 2 |

**Requires re-ingestion:** After deploying, clear `chroma_db/` and restart to populate new metadata fields.

---

## 4. Improve Retrieval Quality

**Status:** :black_square_button: Todo
**Effort:** 1-2 hrs
**File:** `backend/rag_engine.py` — `get_answer()` around line 274

### 4a. Distance Threshold Filtering

ChromaDB returns distances with results but they're currently only logged, not used. Add a threshold to filter out irrelevant results:

- New env var: `RAG_RELEVANCE_THRESHOLD` (default: `1.2`)
- ChromaDB cosine distance: 0 = identical, 2 = opposite
- Filter out results above threshold before sending to LLM
- If all results filtered: fall through to empty context, triggering `__UNKNOWN__`

**Why this helps:** Prevents the LLM from being confused by irrelevant context when users ask about topics not in the knowledge base.

### 4b. Source Diversity

Currently all top-5 results could come from the same file (e.g., 4 chunks from `Boomschors.txt`).

- Fetch `n_results=10` instead of 5
- Cap at max 2 chunks per source file
- Take top 5 from the diversified set

**Why this helps:** For comparison questions ("boomschors vs houtsnippers?"), results from both files will appear instead of one dominating.

### 4c. Reranking (Deferred)

A cross-encoder reranking step would improve relevance but adds a new dependency (~500MB model), latency (~100-200ms), and Docker image size. **Defer until evaluation data shows retrieval quality is the bottleneck.**

---

## 5. Knowledge Base Content Improvements

**Status:** :black_square_button: Todo
**Effort:** 3-4 hrs

### 5a. Expand Thin Files (6 files under 35 lines)

These files are noticeably thinner than well-structured files like `Boomschors.txt` (109 lines):

| File | Current Lines | What to Add |
|---|---|---|
| `Ecopic Paaltjes.txt` | 27 | Dimensions, installation depth, compatibility with borders |
| `Ecolat Borderrand.txt` | 30 | Material properties, comparison with Ekoboard/Recy-Edge |
| `Massieve Kunststof Paaltje.txt` | 32 | Weight, installation guidance, compatible borders |
| `Ekoboard Borderrand.txt` | 34 | Comparison section, detailed installation |
| `Recy-Edge Borderrand.txt` | 33 | Comparison section, detailed installation |
| `Recy-Edge Paaltjes.txt` | ~30 | Compatibility matrix, dimensions |

### 5b. Create Comparison Guides (3 new files)

Users frequently ask comparison questions. Currently there's no dedicated content for this.

**New file: `Vergelijkingsgids Borderranden.txt`**
Compare Ecolat vs Ekoboard vs Recy-Edge: material, dimensions, flexibility, ideal use case, which paaltjes to use.

**New file: `Vergelijkingsgids Bodembedekking.txt`**
Compare Boomschors vs Houtsnippers vs Houtmulch vs Bio Hempcover vs Bio Sheep Wool: material, lifespan, maintenance, ideal applications.

**New file: `Vergelijkingsgids Potgrond en Tuinaarde.txt`**
Guide through: universeel vs biologisch vs moestuin vs veenvrij, when to use potgrond vs tuinaarde.

### 5c. Add Cross-References to Existing Files

Add a `## Gerelateerde producten` section to relevant product files:

- `Anti-worteldoek.txt` → Gronddoekpennen, Boomschors, Houtsnippers
- `Ecolat Borderrand.txt` → Ecopic Paaltjes
- `Ekoboard Borderrand.txt` → Massieve Kunststof Paaltje
- `Boomschors.txt` → Anti-worteldoek, Gronddoekpennen
- `Hydrokorrels.txt` → Potgrond (Algemeen)

Format:
```markdown
## Gerelateerde producten
- **Gronddoekpennen**: Voor het vastzetten van het worteldoek
- **Boomschors**: Populaire deklaag bovenop worteldoek
```

---

## 6. Fix English Language Transparency

**Status:** :black_square_button: Todo
**Effort:** 30 min
**File:** `backend/rag_engine.py` line ~296

**Problem:** The system prompt says "Antwoord in de taal van de gebruiker (Nederlands of Engels)" but the entire knowledge base is Dutch. The LLM can translate Dutch context to English (GPT handles this well), but the prompt should be explicit about it.

**Change:** Add to the TAAL & TOON section:
```
"- De kennisbank is in het Nederlands; vertaal informatie naar Engels wanneer de gebruiker Engels spreekt\n"
```

**What we're NOT doing:** Creating English translations of the knowledge base. Maintaining parallel Dutch/English content is a maintenance nightmare for a single-client deployment. The LLM translation approach is the right call.

---

## Measurement Strategy

Run `evaluate_rag.py` at three checkpoints to track improvement:

| Checkpoint | When | What Changed |
|---|---|---|
| Baseline | After step 5 (framework built) | Nothing — establishes starting point |
| Mid-point | After steps 7-8 (metadata + retrieval) | Chunk metadata, distance filtering, source diversity |
| Final | After steps 9-11 (content + prompt) | Comparison guides, cross-references, English prompt fix |

**Success metrics:**
- Product info pass rate > 80%
- FAQ pass rate > 90%
- Hallucination check pass rate = 100%
- Cross-product recommendation pass rate > 60%
- Average latency < 4 seconds

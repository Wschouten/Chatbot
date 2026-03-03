# Feature 57: Knowledge Base Update Workflow

**Effort:** ~1 hour
**Status:** Todo
**Priority:** Medium (prevents knowledge base drift post-launch)
**Dependencies:** None
**Blocks:** None

---

## Problem

Adding new content to the knowledge base requires knowing the exact steps: create a `.txt` file, re-run ingestion, optionally re-evaluate, redeploy. This process is undocumented and error-prone. Post-launch, as GroundCoverGroup adds new products or FAQ content, there is no repeatable workflow.

Also, the knowledge base evaluation script (`backend/evaluate_rag.py`) must be run manually with no helper script.

---

## Solution

1. **Document** the full knowledge base update process in a runbook
2. **Create** a `scripts/update_knowledge_base.sh` helper that automates ingestion + evaluation in one command
3. **Add** the update cadence to the maintenance checklist in Feature 46

---

## Files to Create/Change

| File | Change |
|------|--------|
| `scripts/update_knowledge_base.sh` | New helper script |
| `improvement-plan/features/57-knowledge-base-workflow.md` | This document (runbook) |

---

## Knowledge Base Update Runbook

### When to Update

| Trigger | Action |
|---------|--------|
| New product launched | Add product description `.txt` file |
| FAQ changes (shipping policy, returns, etc.) | Update relevant `.txt` file |
| Bot returns wrong answer on live site | Identify root cause → update or add `.txt` |
| Weekly log review reveals unanswered questions | Add content to address gaps |

### Step-by-Step Process

**Step 1: Create or edit a knowledge base file**
```
backend/knowledge_base/<ProductOrTopic>.txt
```
- Use plain text (no markdown)
- Follow the format of existing files: product name, description, specs, FAQ
- See `backend/knowledge_base/Houtmulch.txt` as a reference

**Step 2: Test locally**
```bash
# Start the backend (Docker or local)
docker-compose up -d

# OR: run locally
cd backend && python app.py
```

**Step 3: Re-ingest the knowledge base**
```bash
# The backend auto-ingests on startup
# To force re-ingestion without restarting:
curl -X POST http://localhost:5000/api/ingest \
  -H "X-Admin-Key: $ADMIN_API_KEY"
```

**Step 4: Run evaluation**
```bash
cd backend
python evaluate_rag.py
# Check: pass rate should remain at 100%
# Review: evaluation/evaluation_report.md for per-category breakdown
```

**Step 5: Add evaluation questions (if new topic)**

If the new content covers questions not in the test set, add them:
```
backend/evaluation/test_set.json
```
Format:
```json
{
  "question": "Heeft u ook jute zakken?",
  "expected_keywords": ["jute", "zakken", "naturel"],
  "category": "Product Info"
}
```

**Step 6: Commit and deploy**
```bash
git add backend/knowledge_base/ backend/evaluation/
git commit -m "knowledge: add <ProductName> content"
git push origin master
# Railway auto-redeploys
```

---

## Helper Script: `scripts/update_knowledge_base.sh`

```bash
#!/usr/bin/env bash
# update_knowledge_base.sh
# Run this after adding/editing knowledge base files.
# Usage: ./scripts/update_knowledge_base.sh

set -e

echo "=== Knowledge Base Update ==="
echo ""

# 1. Start backend if not running
if ! curl -s http://localhost:5000/health > /dev/null 2>&1; then
    echo "Starting backend..."
    cd backend && python app.py &
    sleep 5
fi

# 2. Re-ingest
echo "Re-ingesting knowledge base..."
curl -s -X POST http://localhost:5000/api/ingest \
    -H "X-Admin-Key: ${ADMIN_API_KEY}" | python3 -m json.tool

# 3. Run evaluation
echo ""
echo "Running RAG evaluation..."
cd backend && python evaluate_rag.py

echo ""
echo "=== Done. Review evaluation_report.md before deploying. ==="
```

Make executable: `chmod +x scripts/update_knowledge_base.sh`

---

## Quality Checklist Before Deploying

- [ ] New content added to `backend/knowledge_base/`
- [ ] Evaluation pass rate still 100% (or improved)
- [ ] No regressions in existing question categories
- [ ] New evaluation questions added for new content (if applicable)
- [ ] Changes committed with descriptive message

---

## Maintenance Cadence

| Task | Frequency |
|------|-----------|
| Review chat logs for unanswered questions | Weekly |
| Update knowledge base based on log review | As needed (within 1 week of identifying gap) |
| Run full evaluation after any update | Every update |
| Add new products to knowledge base | On new product launch |
| Update FAQ / policy content | When policies change |

---

## Verification

```bash
./scripts/update_knowledge_base.sh
# Expected:
# - Ingestion completes with document count > 0
# - Evaluation: 28/28 pass (100%) or higher with new questions
```

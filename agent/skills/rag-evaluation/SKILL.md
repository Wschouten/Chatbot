name: rag-evaluation
description: Evaluates the quality of RAG (Retrieval Augmented Generation) answers against a test dataset.
---

# RAG Evaluation Skill

Use this skill to assess the accuracy and relevance of the chatbot's answers.

## 1. Setup Evaluation Data
Create a JSON file named `test_set.json` in `backend/evaluation/` (create folder if missing).
Format:
```json
[
  {
    "question": "What is the return policy?",
    "expected_answer_keywords": ["30 days", "original packaging", "receipt"],
    "category": "Policy"
  },
  {
    "question": "Where is my order 123?",
    "expected_answer_keywords": ["Processing", "Warehouse A"],
    "category": "Tracking"
  }
]
```

## 2. Run Evaluation
Create and run a script `backend/evaluate_rag.py` that:
1. Imports `RagEngine` from `rag_engine.py`.
2. Initializes the engine (ensure `OPENAI_API_KEY` is loaded).
3. Iterates through `test_set.json`.
4. For each question:
   - getting the answer via `rag.get_answer(question)`.
   - Checks if `expected_answer_keywords` are present in the response (simple keyword match) OR uses an LLM-as-a-judge to score the semantic similarity.
5. Prints a report:
   - Pass/Fail rate per category.
   - Latency (time to answer).
   - "Hallucination check" (did it say "I don't know" when context was missing?).

## 3. Reporting
Generate a markdown summary `evaluation_report.md` with:
- **Date**: [Timestamp]
- **Accuracy**: X% (based on keyword/LLM match)
- **Failed Questions**: List of Qs where actual answer didn't match expected.
- **Recommendations**: e.g., "Add more docs about X", "Adjust chunk size".

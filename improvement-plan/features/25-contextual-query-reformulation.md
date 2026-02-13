# Feature 25: Contextual Query Reformulation

**Track:** Enhancement
**Effort:** 15 min
**Status:** Done
**Dependencies:** None

## Context

Two user-reported issues with answer quality:
1. **Too vague/generic** — The bot says it doesn't know things that ARE in the knowledge base
2. **Poor conversation memory** — The bot seems to forget its own prior responses

Both are caused by the same root issue: follow-up questions get bad RAG retrieval.

## Root Cause

When a user asks a follow-up like "en de prijs?" after discussing houtmulch, the embedding search in `get_answer` (line 340 in `rag_engine.py`) runs on the literal text "en de prijs?" — which matches nothing in ChromaDB. No context is retrieved, so `__UNKNOWN__` is returned (line 555), even though the knowledge base has the answer.

Chat history IS passed to the LLM (lines 564-567), but that happens *after* retrieval has already failed — no context in the prompt means the closed-world system prompt forces the bot to say "I don't know."

## Fix

Add a **query reformulation step** before the RAG search. Use the LLM to rewrite follow-up questions into standalone queries using conversation history.

Example:
- User asks: "Wat is houtmulch?" → bot answers about types and coverage
- User follows up: "en de prijs?"
- **Before fix:** RAG searches for "en de prijs?" → no matches → `__UNKNOWN__`
- **After fix:** Reformulated to "Wat is de prijs van houtmulch?" → matches KB → good answer

This is a standard RAG pattern (known as "contextual query reformulation" or "history-aware retrieval").

## Files to Modify

| File | Action |
|------|--------|
| `backend/rag_engine.py` | **Add** `_reformulate_query` method (~35 lines) after `_get_embedding` (line 77) |
| `backend/rag_engine.py` | **Modify** `get_answer` — add 2-line call after line 340 |
| `backend/evaluate_rag.py` | **Modify** — pass optional `chat_history` from test cases (line 168) |
| `backend/evaluation/test_set.json` | **Add** ~5 follow-up test cases with `chat_history` field |

## Changes

### 1. New method: `_reformulate_query` in `rag_engine.py`

Insert after `_get_embedding` (after line 77):

```python
def _reformulate_query(
    self,
    query: str,
    chat_history: list[dict[str, str]]
) -> str:
    """Reformulate a follow-up question into a standalone query using conversation context."""
    if not self.openai_client:
        return query

    try:
        recent = chat_history[-4:]
        history_text = "\n".join(
            f"{'User' if m['role'] == 'user' else 'Assistant'}: {m['content'][:200]}"
            for m in recent
        )

        response = self.openai_client.chat.completions.create(
            model=self.chat_model,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You rewrite follow-up questions into standalone questions. "
                        "Use the conversation history to resolve pronouns, references, "
                        "and implicit subjects. Keep the language of the user's question "
                        "(Dutch stays Dutch, English stays English). "
                        "If the question is already standalone, return it unchanged. "
                        "Output ONLY the rewritten question, nothing else."
                    )
                },
                {
                    "role": "user",
                    "content": (
                        f"Conversation history:\n{history_text}\n\n"
                        f"Follow-up question: {query}\n\n"
                        "Rewritten standalone question:"
                    )
                }
            ],
            temperature=0.1,
            max_completion_tokens=100
        )
        result = response.choices[0].message.content
        if result:
            reformulated = result.strip()
            logger.debug("Query reformulated: '%s' -> '%s'", query, reformulated)
            return reformulated
        return query
    except Exception as e:
        logger.warning("Query reformulation failed, using original: %s", e)
        return query
```

### 2. Integration in `get_answer`

After line 340 (`search_query = query`), insert:

```python
# Feature 25: Reformulate follow-up questions into standalone queries
if chat_history:
    search_query = self._reformulate_query(query, chat_history)
```

### 3. Evaluation update

**`evaluate_rag.py` line 168:**
```python
chat_history = test_case.get("chat_history", None)
answer = self.rag_engine.get_answer(question, chat_history=chat_history)
```

**`evaluation/test_set.json` — add follow-up test cases:**
```json
{
    "question": "en de prijs?",
    "chat_history": [
        {"role": "user", "content": "Wat is houtmulch?"},
        {"role": "assistant", "content": "Houtmulch is een bodembedekker gemaakt van fijn gemalen hout."}
    ],
    "expected_answer_keywords": ["houtmulch", "prijs"],
    "category": "follow_up",
    "expect_unknown": false
}
```

## Design Decisions

- **Temperature 0.1** — Matches existing translation call; deterministic reformulation
- **Last 4 messages only** — 2 exchanges is enough context; avoids token waste
- **200-char truncation per message** — Prevents long bot answers from bloating the prompt
- **Graceful fallback** — Any failure returns original query; feature is purely additive
- **Original query for final LLM** — Line 553 still uses `query` (not `search_query`), so the user's actual words go to the LLM
- **No cost on first message** — `chat_history` is None/empty for first messages; reformulation is skipped entirely

## Verification

1. `docker-compose up --build`
2. Open chatbot, ask "Wat is houtmulch?" — should get a good answer
3. Follow up with "en de prijs?" — should answer about houtmulch pricing (not "I don't know")
4. Follow up with "hoe dik moet ik dat leggen?" — should answer about houtmulch layer thickness
5. Check logs for `Query reformulated: 'en de prijs?' -> 'Wat is de prijs van houtmulch?'`
6. First messages in new sessions should behave exactly as before

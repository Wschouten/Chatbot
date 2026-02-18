# Testing Context Retention Improvements

## Quick Start

### 1. Start the Backend Server

```bash
cd backend
python app.py
```

Wait for the server to start (you should see "Running on http://127.0.0.1:5000")

### 2. Run the Test Script (Automated)

In a **new terminal**:

```bash
cd backend
python test_context_retention.py
```

The script will:
- ✅ Create a new chat session
- ✅ Run the exact "cacaodoppen" conversation that was failing
- ✅ Check for forbidden phrases like "welk product?" and "geen informatie"
- ✅ Verify the bot maintains context
- ✅ Show colored pass/fail results

### 3. Manual Testing (Optional)

If you prefer to test manually:

1. Open the frontend: `http://localhost:5000` in your browser
2. Start the conversation with:
   - **"Ik heb een vraag over cacaodoppen"**
   - **"Waar kan ik dit voor gebruiken?"**
   - **"Ik heb honden in de tuin. Heb je een alternatief?"**
   - **"cacaodoppen, dat had ik net gezegd"**

3. Expected behavior:
   - ✅ Bot should NEVER ask "welk product?" or "over welk product?"
   - ✅ Bot should NEVER claim "ik heb geen informatie" about cacaodoppen
   - ✅ Bot should reference earlier statements: "Zoals ik eerder noemde..."

---

## Verifying Features in Logs

### Where to Find Logs

Log file location: `backend/logs/chat_conversations_YYYYMMDD.log`

For today: `backend/logs/chat_conversations_$(date +%Y%m%d).log`

### What to Look For

#### ✅ Feature 01: System Prompt Enhancement
- **No direct logs** (this is prompt engineering)
- **Verify:** Bot responses reference earlier statements
- **Verify:** No "what product?" questions

#### ✅ Feature 02: Query Reformulation
Look for:
```
Query reformulated: 'Heb je een alternatief?' -> 'Heb je een alternatief voor cacaodoppen voor honden?'
```

**Expected:** Product names preserved in reformulated queries

#### ✅ Feature 03: Entity Extraction
Look for:
```
Extracted conversation entities: ['cacaodoppen', 'honden']
```

**Expected:** Product names and key entities extracted from conversation

#### ✅ Feature 04: Conversation Summary
- **No direct logs** (injected into prompt)
- **Verify:** Bot doesn't contradict itself
- **Verify:** Bot references earlier statements when context is empty

#### ✅ Feature 05: RAG Caching
Look for:
```
Using cached context for query: 'cacaodoppen'
```

**Expected:** Second query about same product uses cached results

---

## Checking Logs with Commands

### View all feature activity for a session

```bash
grep -E "(Query reformulated|Extracted conversation entities|Enhanced search query|Using cached context)" backend/logs/chat_conversations_*.log | tail -20
```

### Check for specific features

**Query Reformulation:**
```bash
grep "Query reformulated" backend/logs/chat_conversations_*.log | tail -5
```

**Entity Extraction:**
```bash
grep "Extracted conversation entities" backend/logs/chat_conversations_*.log | tail -5
```

**Enhanced Queries:**
```bash
grep "Enhanced search query with entities" backend/logs/chat_conversations_*.log | tail -5
```

**Cache Hits:**
```bash
grep "Using cached context" backend/logs/chat_conversations_*.log | tail -5
```

---

## Expected Test Results

### ✅ Success Indicators

1. **No "what product?" questions** - Bot remembers what's being discussed
2. **No false ignorance claims** - Bot doesn't say "I don't know" about things it just explained
3. **Entity extraction logs** - Shows product names being tracked
4. **Query reformulation logs** - Shows pronouns being resolved
5. **Cache hits** - Shows efficient reuse of RAG results

### ❌ Failure Indicators

1. Bot asks "Over welk product hebben we het?"
2. Bot says "Ik heb geen informatie over cacaodoppen" after discussing it
3. Missing logs for entity extraction or query reformulation
4. Bot contradicts previous statements

---

## Troubleshooting

### Server Won't Start

**Issue:** `Address already in use`
**Fix:** Kill existing process
```bash
# Windows
netstat -ano | findstr :5000
taskkill /PID <PID> /F

# Linux/Mac
lsof -ti:5000 | xargs kill -9
```

### No Logs Generated

**Issue:** Log directory doesn't exist
**Fix:**
```bash
mkdir -p backend/logs
```

### Test Script Fails to Connect

**Issue:** Server not running or wrong port
**Fix:**
1. Check server is running: `curl http://localhost:5000/api/health`
2. Check port in `.env` matches test script (default: 5000)

### Features Not Working

**Issue:** Changes not loaded
**Fix:** Restart the server
```bash
# Stop server (Ctrl+C)
# Start again
python app.py
```

---

## Performance Expectations

| Metric | Target | Measurement |
|--------|--------|-------------|
| Cache hit rate | >30% | Count cache hit logs vs total queries |
| Entity extraction accuracy | >85% | Manual review of extracted entities |
| Query reformulation quality | >90% | Reformulated queries include product names |
| Self-contradiction rate | 0% | No contradictions in test conversation |
| False ignorance rate | 0% | No "I don't know" when info was given |

---

## Next Steps After Testing

If tests pass:
1. ✅ Commit changes to git
2. ✅ Deploy to production
3. ✅ Monitor production logs for 24 hours
4. ✅ Update feature status files

If tests fail:
1. ❌ Check logs for error details
2. ❌ Review specific failing feature
3. ❌ Debug and fix issue
4. ❌ Re-test

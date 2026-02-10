# Feature 22: Post-Launch Monitoring

**Track:** Operations
**Effort:** 30 min setup + ongoing
**Status:** Todo
**Dependencies:** Feature 21 (Shopify Widget Integration — store must be live with the widget)

## Context

Once the chatbot is live on the Shopify store, ongoing monitoring is needed to catch issues early: downtime, API cost spikes, degraded answer quality, and user experience problems. This feature covers the initial monitoring setup during the first week after launch.

## Steps

### 1. Set up uptime monitoring

- Create a free [UptimeRobot](https://uptimerobot.com) account
- Add a new HTTP(s) monitor for `https://chat.your-store.com/health`
- Set check interval to 5 minutes
- Configure email alerts for downtime

### 2. Monitor Railway logs (first week)

- Check Railway dashboard logs daily for the first week
- Watch for:
  - Python exceptions / tracebacks
  - Gunicorn worker timeouts (indicates queries taking >120s)
  - Memory usage trends (ChromaDB + 2 workers should stay under 512MB)

### 3. Monitor OpenAI API usage

- Check [OpenAI usage dashboard](https://platform.openai.com/usage) daily for the first week
- Verify costs are within the expected ~$5-20/month range
- Set up OpenAI usage alerts/limits if available

### 4. Run RAG evaluation suite

- After deployment is stable (1-2 days), run the RAG evaluation suite against the production endpoint
- Compare results with the pre-deployment baseline (100% pass rate)
- Investigate any regressions

```bash
python backend/evaluate_rag.py
```

### 5. Review chat logs

- Check `backend/logs/` (via Railway volume) for conversation patterns
- Look for:
  - Frequently asked questions not in the knowledge base
  - Incorrect or unhelpful answers
  - Users getting stuck in conversation flows
  - Escalation rate (how often users request human help)

## Verification

1. UptimeRobot is configured and sending test alerts
2. Railway logs are accessible and show no recurring errors
3. OpenAI usage is within expected range
4. RAG evaluation passes at the same rate as pre-deployment
5. No critical issues found in chat log review

## Notes

- UptimeRobot free tier allows 50 monitors with 5-minute intervals — more than sufficient
- If Railway logs show consistent memory pressure, consider increasing the Railway plan or reducing gunicorn workers to 1
- Chat log review should become a weekly habit, not just a first-week task
- Consider adding new Q&A pairs to the knowledge base based on real user questions that the bot struggles with

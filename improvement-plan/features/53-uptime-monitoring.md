# Feature 53: Uptime Monitoring Setup

**Effort:** ~15 min
**Status:** Todo
**Priority:** High (production ops — catch outages before customers do)
**Dependencies:** Feature 46 (go-live — need live Railway URL)
**Blocks:** None

---

## Problem

Once the chatbot is live on Railway, there is no automated alerting if the service goes down. Issues could go undetected for hours. The `/health` endpoint already exists and returns structured health data — it just needs a monitor watching it.

---

## Solution

Set up UptimeRobot (free tier) to poll `/health` every 5 minutes and send email/Slack alerts on failure.

---

## Steps

### 1. Get the Railway URL

After Feature 46 (go-live), you have a URL like:
- `https://groundcover-chatbot.up.railway.app` (Railway-provided), or
- `https://chat.groundcovergroup.nl` (custom domain)

Use whichever is live.

### 2. Create UptimeRobot Account

1. Go to [uptimerobot.com](https://uptimerobot.com) and sign up (free)
2. Verify your email address

### 3. Add HTTP Monitor

1. Click **"+ Add New Monitor"**
2. Fill in:
   - **Monitor Type:** `HTTP(s)`
   - **Friendly Name:** `GroundCover Chatbot`
   - **URL:** `https://<your-railway-url>/health`
   - **Monitoring Interval:** `5 minutes`
3. Under **"Alert Contacts"**, add your email (and optionally a Slack webhook)
4. Click **"Create Monitor"**

### 4. Verify the Monitor

1. In the UptimeRobot dashboard, confirm the monitor shows **"Up"** with a green status
2. Click the monitor → verify the response time graph appears
3. Optionally: temporarily test alerting by checking "Pause" → you'll receive an "Alert: Your monitor is down" email → unpause

### 5. Optional: Add a Status Page

UptimeRobot offers a free public status page. Useful for sharing uptime with the team:
1. Go to **"Status Pages"** → **"Add Status Page"**
2. Add the chatbot monitor to it
3. Share the URL with stakeholders

---

## What the `/health` Endpoint Returns

```json
{
  "status": "ok",
  "document_count": 1234,
  "rag_engine": "initialized",
  "email_escalation": "configured",
  "shipping_api": "mock_mode",
  "data_retention": "enabled"
}
```

UptimeRobot marks the monitor **"Up"** when it receives HTTP 200. It marks it **"Down"** on any non-200 response or connection timeout.

---

## Alert Configuration (Recommended)

| Alert type | When | Suggested setup |
|------------|------|-----------------|
| Down alert | Immediately on first failure | Email to developer + store owner |
| Up alert | When service recovers | Email (confirms issue resolved) |
| Weekly report | Every Monday | Optional summary email |

---

## Maintenance

- No code changes required
- UptimeRobot monitors persist indefinitely on the free tier
- If Railway URL changes (custom domain added), update the monitor URL
- Check dashboard monthly: Railway logs + UptimeRobot history should agree

---

## Verification

- [ ] Monitor created and showing green "Up" status
- [ ] Email alert received on test downtime (pause → unpause test)
- [ ] Monitor URL matches actual Railway deployment URL
- [ ] Alert contacts include at least one active email address

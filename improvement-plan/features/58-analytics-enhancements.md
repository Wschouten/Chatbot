# Feature 58: Analytics Dashboard Enhancements

**Effort:** ~2-3 hours
**Status:** Todo
**Priority:** Low (business intelligence — useful once traffic volume grows)
**Dependencies:** None (uses existing admin DB data)
**Blocks:** None

---

## Problem

The current dashboard shows aggregate stats (total conversations, average messages, escalation rate) but no time-series data. You can't answer questions like:
- "Are escalations increasing week-over-week?"
- "Which days/hours get the most traffic?"
- "Is the unknown/flagged rate improving after a knowledge base update?"

---

## Solution

Add a time-series analytics section to the dashboard with:
1. **Weekly conversation volume** — bar chart of conversations per week (last 8 weeks)
2. **Escalation rate trend** — line chart showing escalation % week-over-week
3. **Top issue categories** — breakdown of `unknown_flagged` conversations by inferred topic (label distribution)
4. **Busiest hours** heatmap — already partially exists; improve visualisation

---

## Files Changed

| File | Change |
|------|--------|
| `backend/app.py` | New `GET /admin/api/stats/trends` endpoint |
| `portal/js/storage.js` | New `fetchTrends()` method |
| `portal/js/app.js` | New `renderTrends()` chart renderer |
| `frontend/templates/portal.html` | Charts section in dashboard view |
| `frontend/static/portal.css` | Chart container styles |

---

## Backend: New Stats Endpoint

`GET /admin/api/stats/trends`

Response:
```json
{
  "weekly_volume": [
    {"week": "2026-01-27", "count": 42},
    {"week": "2026-02-03", "count": 58},
    {"week": "2026-02-10", "count": 61}
  ],
  "weekly_escalations": [
    {"week": "2026-01-27", "escalation_rate": 0.12},
    {"week": "2026-02-03", "escalation_rate": 0.09},
    {"week": "2026-02-10", "escalation_rate": 0.08}
  ],
  "top_labels": [
    {"label": "shipping-inquiry", "count": 34},
    {"label": "order-tracking", "count": 28},
    {"label": "complaint", "count": 9}
  ],
  "hourly_distribution": [0, 0, 0, 1, 2, 5, 12, 28, ...]
}
```

This endpoint reads directly from the log files (for timestamps) and `portal.db` (for labels/escalations). No new DB tables needed.

---

## Frontend: Chart Implementation Options

### Option A: Pure CSS/SVG (no dependencies)
Build simple bar/line charts with inline SVG. Matches the existing "no external JS libraries" pattern of the portal.

### Option B: Chart.js (lightweight, ~200KB)
Load Chart.js from CDN. Provides polished interactive charts with minimal code.

**Recommendation: Option A (SVG)** for consistency with the existing portal style. The charts are simple enough that SVG is sufficient.

---

## Dashboard Layout (with enhancements)

```
┌──────────────────────────────────────────────────┐
│  DASHBOARD                                        │
├──────────────┬──────────────┬────────────────────┤
│ Total Convs  │ Avg Messages │ Escalation Rate    │ ← existing stat cards
├──────────────┴──────────────┴────────────────────┤
│  Weekly Conversation Volume (last 8 weeks)        │ ← new
│  ████ ████ ██████ █████ ████████ ██████ ███ ████ │
├───────────────────────────────────────────────────┤
│  Escalation Rate Trend                            │ ← new
│  ╲___/‾‾\_____/‾\___/‾‾‾‾‾‾‾‾‾              │
├───────────────────────────────────────────────────┤
│  Top Labels          │  Hourly Traffic            │ ← new / improved
│  shipping-inquiry 34 │  [heatmap grid]            │
│  order-tracking   28 │                            │
└─────────────────────────────────────────────────-┘
```

---

## Implementation Notes

- Trend data is computed from log file timestamps + SQLite metadata at request time (no pre-aggregation needed for low traffic volumes)
- If conversation volume grows large (>10k), add a materialized stats table to avoid re-scanning all log files on each request
- Charts are rendered on dashboard load; no real-time updates needed

---

## Verification

1. Open admin portal → Dashboard view
2. Verify weekly volume chart shows bars for the last 8 weeks
3. Verify escalation trend line is present and non-zero
4. Verify top labels list matches the labels visible in the Conversations view
5. Verify charts render correctly with zero data (empty state: "No data yet")
6. Verify API endpoint: `curl -H "X-Admin-Key: $KEY" /admin/api/stats/trends` returns valid JSON

# Feature 46: Post-Launch Verification

**Effort:** ~15 min
**Status:** Todo
**Priority:** High (confirms production readiness)
**Dependencies:** Feature 45 (Shopify widget deployed)
**Blocks:** None (this is the final step)

---

## Problem

Need to verify the complete production stack works end-to-end: Shopify widget communicating with Railway backend, admin portal accessible, email escalation functional, and monitoring in place.

---

## Verification Checklist

### Chatbot (from Shopify store)

- [ ] Chat bubble visible on storefront
- [ ] Dutch conversation works with relevant answers
- [ ] English conversation works with relevant answers
- [ ] Follow-up questions maintain context
- [ ] Shipping order lookup works (mock mode or real)
- [ ] GDPR consent appears on first interaction
- [ ] No CORS errors in browser console
- [ ] Widget responsive on mobile

### Admin Portal (from Railway URL)

- [ ] Portal loads at `https://<railway-url>/portal`
- [ ] Login works with ADMIN_API_KEY
- [ ] Conversations from Shopify visitors appear in list
- [ ] Labels, notes, ratings persist across page refresh
- [ ] Metadata persists after clearing browser localStorage
- [ ] Search and filtering work
- [ ] Export (JSON/CSV) works

### Email Escalation

- [ ] Trigger escalation flow via chat
- [ ] Email arrives at configured SMTP_TO_EMAIL
- [ ] Email contains conversation context and customer message

### Health & Monitoring

- [ ] `https://<railway-url>/health` returns 200 with healthy status
- [ ] Set up UptimeRobot or similar to monitor `/health` endpoint
  - URL: `https://<railway-url>/health`
  - Interval: 5 minutes
  - Alert: Email or Slack notification on failure
- [ ] Railway dashboard shows healthy deployment
- [ ] Check Railway logs for any errors or warnings

### Shipping API (when StatusWeb whitelists IP)

- [ ] Add `SHIPPING_API_KEY` and `SHIPPING_API_PASSWORD` to Railway variables
- [ ] Test real order lookup: "Waar is mijn bestelling <real-order-number>?"
- [ ] Verify real tracking status returned
- [ ] Health endpoint shows `shipping_api: configured` instead of `mock_mode`

---

## Ongoing Maintenance

| Task | Frequency | Description |
|------|-----------|-------------|
| Check health endpoint | Automated (UptimeRobot) | Continuous monitoring |
| Review chat logs | Weekly | Check for unanswered questions, update knowledge base |
| Test email escalation | Weekly | Verify SMTP still working |
| Rotate SMTP App Password | Every 6 months | Azure AD security requirement |
| Update knowledge base | As needed | Add new products, update FAQ |
| Review Railway costs | Monthly | Monitor usage and billing |
| Check OpenAI usage | Monthly | Monitor API quota and costs |

---

## Go-Live Complete

When all checklist items pass, the chatbot is live and operational. Share the following with the team:

- **Chatbot:** Embedded on Shopify store (automatic for all visitors)
- **Admin Portal:** `https://<railway-url>/portal` (login with ADMIN_API_KEY)
- **Health Monitor:** `https://<railway-url>/health`
- **Support Email:** Escalations go to SMTP_TO_EMAIL

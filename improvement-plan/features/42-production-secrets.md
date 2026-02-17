# Feature 42: Production Secrets Setup

**Effort:** ~30 min
**Status:** Todo
**Priority:** High (blocks deployment)
**Dependencies:** None (can start anytime)
**Blocks:** Feature 43

---

## Problem

Production deployment requires real API keys and credentials that have not yet been generated or configured.

---

## Required Secrets

### 1. ADMIN_API_KEY (generate new)

```bash
openssl rand -hex 32
```

Store the result securely. This is used for:
- Admin portal login
- All `/admin/api/*` endpoints
- Email escalation triggers

### 2. OPENAI_API_KEY (confirm production key)

- Verify the production OpenAI API key is active and has sufficient quota
- **Important:** The dev key may have been flagged as exposed. Generate a new one at https://platform.openai.com/api-keys
- Required models: `gpt-4o-mini` (chat) and `text-embedding-3-small` (embeddings)

### 3. SMTP Credentials (Office 365)

- **SMTP_SERVER:** `smtp.office365.com`
- **SMTP_PORT:** `587`
- **SMTP_FROM_EMAIL:** Your sending email address
- **SMTP_PASSWORD:** Office 365 App Password (NOT your regular password)
  - Azure AD > Security > App Passwords > Generate
  - Requires MFA enabled on the account
- **SMTP_TO_EMAIL:** Support inbox that receives escalation emails

### 4. ALLOWED_ORIGINS (Shopify domains)

List all domains where the widget will be embedded:
```
ALLOWED_ORIGINS=https://your-store.myshopify.com,https://www.your-custom-domain.com
```

### 5. Shipping API (when StatusWeb whitelists IP)

- **SHIPPING_API_KEY:** Provided by Van Den Heuvel / StatusWeb
- **SHIPPING_API_PASSWORD:** Provided by Van Den Heuvel / StatusWeb
- Until IP is whitelisted, leave these empty — the app auto-falls back to mock mode

---

## Where to Store

| Location | Purpose |
|----------|---------|
| Railway Dashboard > Variables | Production runtime |
| Password Manager | Backup / documentation |
| **NOT** in `.env` file in git | Security |

---

## Verification

- [ ] ADMIN_API_KEY generated and saved
- [ ] OPENAI_API_KEY confirmed working (test with a simple API call)
- [ ] SMTP App Password created and tested
- [ ] Shopify domain(s) confirmed for ALLOWED_ORIGINS
- [ ] All secrets documented in password manager
- [ ] No secrets committed to git (`git diff` check)

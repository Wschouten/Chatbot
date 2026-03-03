# Feature 54: Shipping API Live Integration

**Effort:** ~30 min (config + testing, once IP is whitelisted)
**Status:** Blocked (waiting for StatusWeb IP whitelist)
**Priority:** High (customers currently see mock tracking data)
**Dependencies:** Feature 46 (go-live), StatusWeb whitelisting Railway's outbound IP
**Blocks:** None

---

## Problem

The shipping API (`backend/shipping_api.py`) is running in mock mode because StatusWeb requires IP whitelisting and Railway's outbound IP hasn't been submitted yet. Real order tracking lookups return placeholder data instead of live status.

The health endpoint currently shows:
```json
"shipping_api": "mock_mode"
```

It should show:
```json
"shipping_api": "configured"
```

---

## Prerequisites

1. **StatusWeb IP whitelist approved** — you must submit Railway's static outbound IP to StatusWeb and receive confirmation
2. **Feature 46 complete** — chatbot must be live on Railway before testing live tracking

---

## Steps

### 1. Get Railway's Outbound IP Address

In the Railway dashboard:
1. Go to your service → **Settings** → **Networking**
2. Note the **outbound IP address** (static IPs are available on Railway Pro plans; Hobby plan uses shared egress)

> **If Railway doesn't provide a static IP:** Consider Railway Pro, or use a fixed-IP proxy (e.g., QuotaGuard Static). StatusWeb needs a stable IP to whitelist.

### 2. Submit Whitelist Request to StatusWeb

Email or submit via their portal:
- **Your outbound IP:** (from step 1)
- **Purpose:** Order tracking API for GroundCoverGroup chatbot
- **Expected volume:** Low (only triggered by customer tracking queries)

Wait for confirmation before proceeding.

### 3. Add Environment Variables to Railway

Once whitelisted, go to Railway dashboard → your service → **Variables** tab, and add:

| Variable | Value | Notes |
|----------|-------|-------|
| `SHIPPING_API_KEY` | *(from StatusWeb)* | Your API key |
| `SHIPPING_API_PASSWORD` | *(from StatusWeb)* | Your API password |

Railway auto-redeploys after env var changes.

### 4. Verify Health Endpoint

After redeployment, check:
```
https://<railway-url>/health
```

Confirm the response shows:
```json
"shipping_api": "configured"
```

If it still shows `"mock_mode"`, the env vars weren't picked up — check Railway logs for startup errors.

### 5. Test Live Order Lookup

Send a real order tracking message in the chatbot:
```
Waar is mijn bestelling <real-order-number>?
```

Expected: real tracking status from StatusWeb (not mock data).

Also test edge cases:
- Non-existent order number → chatbot handles gracefully
- Invalid format → chatbot asks for valid order number

---

## Fallback: If Static IP Is Not Available

If Railway can't provide a static outbound IP and StatusWeb won't whitelist a dynamic range:

**Option A: Railway Pro plan** (~$20/month) — provides dedicated networking
**Option B: Fixed-IP proxy** — route outbound requests through a service like QuotaGuard Static (~$19/month) which provides a fixed IP

The code change for Option B would be in `backend/shipping_api.py` — add proxy support to the `requests` calls:
```python
proxies = {"https": os.getenv("HTTPS_PROXY")}
response = requests.get(url, proxies=proxies, ...)
```

---

## Files Affected (if proxy needed)

| File | Change |
|------|--------|
| `backend/shipping_api.py` | Add `HTTPS_PROXY` env var support to requests calls |
| `backend/.env.example` | Document `HTTPS_PROXY` variable |

No code changes needed if Railway static IP works directly.

---

## Verification

- [ ] Health endpoint shows `"shipping_api": "configured"`
- [ ] Real order lookup returns live tracking status
- [ ] Non-existent order handled gracefully (no 500 error)
- [ ] No SHIPPING_API_KEY visible in Railway logs (secrets not logged)

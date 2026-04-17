# Plan: Replace Zapier WISMO with Direct Shopify Admin API

## Context

The WISMO (Where Is My Order?) flow verifies a user's order by matching their order number against
their email address. This was originally built using a Zapier webhook because **Shopify Admin API
access was not available at the time**. Now that access is available, Zapier is no longer needed.

The Zapier approach was also fundamentally broken: Zapier's "Catch Hook" trigger returns
`{"status": "success"}` immediately and runs the Zap asynchronously in the background. The chatbot
calls `requests.post(..., timeout=15)` and reads the JSON response — so it always received
`{"status": "success"}`, never the actual verification result. The WISMO feature has therefore
**never worked in production**.

---

## Options Compared

### Option A — Fix Zapier with a callback endpoint (rejected)
Add a `/wismo-callback` endpoint to the chatbot. The Zap POSTs the result back to it. The chatbot
polls a temporary in-memory store waiting for the callback.

**Why rejected:** Requires polling logic, a shared in-memory store, a new public endpoint, and
Zapier still has a 2–5s processing delay. Adds significant complexity to solve a problem that
direct API access eliminates entirely.

### Option B — Use a Shopify Python library (rejected)
Install `ShopifyAPI` (pip package) and use its ORM-style interface.

**Why rejected:** Adds a library dependency for a single GET request to one endpoint. The
`requests` library already handles this perfectly. No need for an extra abstraction layer.

### Option C — Use Shopify GraphQL API (rejected)
Query the GraphQL Admin API instead of REST.

**Why rejected:** GraphQL is more powerful but significantly more complex for a simple order
lookup. REST is sufficient, well-documented, and easier to debug.

### Option D — Direct Shopify Admin REST API (chosen)
Replace `_call_zapier_wismo()` with `_verify_shopify_order()` that calls:
`GET https://{shop}.myshopify.com/admin/api/2024-01/orders.json?name=%23{order_number}&status=any`

**Why this is best:**
- Synchronous — chatbot reads the result in a single HTTP call, no workarounds
- No new dependencies — `requests` is already installed
- No new infrastructure — no Zap to maintain or pay for
- Simple — replaces one function, one call site, two env vars
- Secure — uses an Admin API token with `read_orders` scope only
- Same return contract `{"outcome": "ok|not_found|error"}` — caller code unchanged

---

## Implementation Plan

### Step 1 — Create a Shopify Admin API app

In Shopify Admin → Settings → Apps and sales channels → Develop apps:
1. Click "Allow custom app development" if not already enabled
2. Create a new app (e.g. "GCG Chatbot WISMO")
3. Under "Configuration" → "Admin API integration" → add scope: `read_orders`
4. Install the app
5. Copy the **Admin API access token** (shown only once — save it immediately)
6. Note your shop subdomain (e.g. `groundcover` from `groundcover.myshopify.com`)

---

### Step 2 — Replace `_call_zapier_wismo()` in `backend/app.py` (lines 773–798)

Delete the entire existing function and replace with:

```python
def _verify_shopify_order(order_number: str, email: str) -> dict:
    """Verify a Shopify order number + email via the Admin REST API.
    Returns: {"outcome": "ok"} | {"outcome": "not_found"} | {"outcome": "error"}
    """
    shop_name = os.getenv('SHOPIFY_SHOP_NAME', '').strip()
    access_token = os.getenv('SHOPIFY_ACCESS_TOKEN', '').strip()

    if not shop_name or not access_token:
        logger.warning("SHOPIFY_SHOP_NAME or SHOPIFY_ACCESS_TOKEN not configured")
        return {"outcome": "error"}

    # Strip leading '#' — query param expects bare number, we prepend %23 in the URL
    bare_number = order_number.lstrip('#')
    url = (
        f"https://{shop_name}.myshopify.com/admin/api/2024-01/orders.json"
        f"?name=%23{bare_number}&status=any"
    )
    headers = {
        "X-Shopify-Access-Token": access_token,
        "Content-Type": "application/json",
    }

    try:
        resp = requests.get(url, headers=headers, timeout=15)
        resp.raise_for_status()
        orders = resp.json().get("orders", [])
        if not orders:
            logger.info("Shopify WISMO: order %r not found", order_number)
            return {"outcome": "not_found"}
        order_email = (orders[0].get("email") or "").lower().strip()
        if order_email == email.lower().strip():
            return {"outcome": "ok"}
        logger.info(
            "Shopify WISMO: email mismatch for order %r",
            order_number,
        )
        return {"outcome": "not_found"}
    except requests.exceptions.Timeout:
        logger.error("Shopify WISMO timeout for order %s", order_number)
        return {"outcome": "error"}
    except requests.exceptions.HTTPError as exc:
        logger.error("Shopify WISMO HTTP error for order %s: %s", order_number, exc)
        return {"outcome": "error"}
    except requests.exceptions.RequestException as exc:
        logger.error("Shopify WISMO request failed: %s", exc)
        return {"outcome": "error"}
```

**No new imports needed** — `requests` (line 26) and `os` (line 4) are already imported.

---

### Step 3 — Update the call site in `backend/app.py` (lines 1023–1025)

```python
# Before (line 1023):
# Call Zapier to verify order number + email (Feature 63)
zapier_result = _call_zapier_wismo(shopify_order_number, email_input)

# After:
# Verify order number + email directly against Shopify Admin API (Feature 63)
zapier_result = _verify_shopify_order(shopify_order_number, email_input)
```

Everything else in the caller block (lines 1026–1087) is **unchanged** — the return contract
`{"outcome": "ok|not_found|error"}` is identical.

---

### Step 4 — Update `backend/.env.example` (lines 164–169)

Remove:
```
# =============================================================================
# WISMO (Where Is My Order?) Zapier Webhook
# =============================================================================

# Zapier webhook URL to verify a Shopify order number + email combination
ZAPIER_WEBHOOK_URL_WISMO=https://hooks.zapier.com/hooks/catch/23007688/u0qy8uk/
```

Replace with:
```
# =============================================================================
# WISMO (Where Is My Order?) — Shopify Admin API
# =============================================================================

# Shopify store subdomain (the part before .myshopify.com)
# Example: if your store is groundcover.myshopify.com, set this to: groundcover
SHOPIFY_SHOP_NAME=your-shop-name

# Shopify Admin API access token
# Generate at: Shopify Admin -> Settings -> Apps and sales channels -> Develop apps
# Required scopes: read_orders
SHOPIFY_ACCESS_TOKEN=shpat_YOUR_TOKEN_HERE
```

---

### Step 5 — Update Railway environment variables

In the Railway dashboard:
1. **Remove** `ZAPIER_WEBHOOK_URL_WISMO`
2. **Add** `SHOPIFY_SHOP_NAME` = `groundcover` (your actual subdomain)
3. **Add** `SHOPIFY_ACCESS_TOKEN` = the token from Step 1
4. Redeploy — no pip install needed

---

### Step 6 — Update memory file

Update `wismo.md` in project memory to reflect the completed implementation and remove the
on-hold status.

---

## Edge Cases Handled

| Scenario | Outcome | Notes |
|---|---|---|
| Env vars missing | `error` | Warning logged |
| Order not found in Shopify | `not_found` | Empty `orders` array |
| Order found, email mismatch | `not_found` | Same message as not found — prevents order enumeration |
| Shopify 401 bad token | `error` | `HTTPError` catch |
| Shopify 429 rate limit | `error` | `HTTPError` catch; one call per user interaction, rate limiting unlikely |
| Network timeout (15s) | `error` | Same timeout as Zapier had |
| Any other network failure | `error` | `RequestException` catch |

---

## Files Modified

| File | Lines | Change |
|---|---|---|
| `backend/app.py` | 773–798 | Replace `_call_zapier_wismo` with `_verify_shopify_order` |
| `backend/app.py` | 1023 | Update comment |
| `backend/app.py` | 1025 | Rename function call (one word change) |
| `backend/.env.example` | 164–169 | Remove Zapier block, add Shopify block |

---

## Verification

1. Set `SHOPIFY_SHOP_NAME` and `SHOPIFY_ACCESS_TOKEN` in local `.env`
2. Run the chatbot locally: `python app.py`
3. Send a tracking intent message (e.g. "waar is mijn bestelling")
4. Enter a real order number from your Shopify store
5. Enter the correct email → should get ✅ verified response
6. Enter a wrong email → should get ❌ not found response
7. Enter a non-existent order number → should get ❌ not found response
8. Temporarily break the token → should get technical error message

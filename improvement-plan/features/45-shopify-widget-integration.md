# Feature 45: Shopify Widget Integration

**Effort:** ~15 min
**Status:** Todo
**Priority:** High (customer-facing go-live)
**Dependencies:** Feature 44 (Railway deployed and verified)
**Blocks:** Feature 46

---

## Problem

The chatbot needs to be embedded on the GroundCoverGroup Shopify store as a floating chat widget.

---

## Steps

### 1. Get Widget Script URL

After Railway deployment (Feature 44), the widget script is served at:
```
https://<railway-url>/static/widget.js
```

### 2. Add Widget to Shopify Theme

1. Log in to Shopify admin
2. Go to **Online Store > Themes**
3. Click **Actions > Edit code** on the active theme
4. Open **Layout/theme.liquid**
5. Add the widget script before the closing `</body>` tag:

```html
<!-- GroundCoverGroup Chat Widget -->
<script
  src="https://<railway-url>/static/widget.js"
  data-api-url="https://<railway-url>"
  data-brand="GroundCoverGroup"
  data-position="bottom-right"
  data-primary-color="#2C5E2E"
  data-welcome="Hallo! Ik ben de GroundCoverGroup assistent. Hoe kan ik je helpen?"
  data-privacy-url="/pages/privacy-policy"
></script>
```

6. Click **Save**

### 3. Update CORS Configuration

In Railway dashboard, update `ALLOWED_ORIGINS` to include your Shopify domains:

```
ALLOWED_ORIGINS=https://your-store.myshopify.com,https://www.your-custom-domain.com,https://<railway-url>
```

Railway will auto-redeploy after environment variable change.

### 4. Widget Customization (optional)

The widget supports these `data-*` attributes:

| Attribute | Default | Description |
|-----------|---------|-------------|
| `data-api-url` | (required) | Backend API URL |
| `data-brand` | GroundCoverGroup | Widget title text |
| `data-position` | bottom-right | Widget position on page |
| `data-primary-color` | #2C5E2E | Theme color |
| `data-welcome` | (Dutch greeting) | Welcome message |
| `data-privacy-url` | — | Link to privacy policy |

---

## Verification

1. Visit your Shopify store in a browser
2. Verify: Chat bubble appears in bottom-right corner
3. Click the bubble — widget opens
4. Test a Dutch conversation: "Wat is houtmulch?"
5. Test an English conversation: "What products do you have?"
6. Test shipping flow: "Waar is mijn bestelling 12345?"
7. Open browser DevTools console — verify no CORS errors
8. Test on mobile — verify widget is responsive
9. Navigate between pages — verify widget persists

### Known Limitations

- Widget will **not** appear on Shopify checkout pages (Shopify restriction)
- Widget loads after page content (non-blocking `<script>` tag)

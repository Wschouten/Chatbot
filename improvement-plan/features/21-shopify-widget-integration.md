# Feature 21: Shopify Widget Integration

**Track:** Integration
**Effort:** 15-30 min
**Status:** Todo
**Dependencies:** Feature 20 (Railway Hosting — needs a live public URL with HTTPS)

## Context

The chatbot widget needs to be embedded on the Shopify store. This is done by adding a `<script>` tag to the store's theme layout file. The widget JS is served from the Railway-hosted backend, so the hosting must be live before this step.

## Steps

### 1. Open theme editor

Shopify Admin > Online Store > Themes > Edit Code

### 2. Edit `Layout/theme.liquid`

Add the following snippet before the closing `</body>` tag:

```html
<script src="https://chat.your-store.com/widget.js"
        data-api-url="https://chat.your-store.com"
        data-brand="GroundCoverGroup"
        data-position="bottom-right"
        data-primary-color="#2C5E2E"
        data-welcome="Hallo! Hoe kan ik je helpen?"
        data-privacy-url="/pages/privacy-policy">
</script>
```

Replace `chat.your-store.com` with the actual Railway custom domain from Feature 20.

### 3. Test across scenarios

Run through the following test matrix:

| Test | What to check |
|------|---------------|
| Desktop browser | Widget appears bottom-right, chat flow works |
| Mobile browser | Widget doesn't overlap sticky headers/footers |
| Incognito mode | GDPR consent prompt appears before first message |
| Dutch query | Response is in Dutch |
| English query | Response is in English |
| Browser console | No CORS errors, no mixed-content warnings |
| Checkout page | Widget does NOT appear (expected — Shopify restricts scripts) |
| Z-index conflicts | Widget floats above all theme elements |

## Verification

1. Chat bubble is visible on all store pages (except checkout)
2. Clicking the bubble opens the chat window
3. Full conversation flow works: greeting > question > answer
4. Escalation flow works: unanswerable question > request human > name > email > confirmation
5. No JavaScript errors in browser console
6. No CORS errors (Railway `ALLOWED_ORIGINS` matches the Shopify domain)
7. Widget is responsive on mobile

## Notes

- The widget will NOT appear on Shopify checkout pages — this is a Shopify platform restriction and is expected
- There may be two consent prompts visible (Shopify's cookie banner + chatbot GDPR consent) — this is acceptable for now
- If z-index conflicts occur with the theme, the widget's z-index can be adjusted in `frontend/static/widget.js`
- `data-primary-color="#2C5E2E"` matches the GroundCover brand green; update if store branding differs

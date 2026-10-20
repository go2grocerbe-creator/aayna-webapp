# AAYNA public brand pages (temporary, pre-launch)

A small static site that gives `shopaayna.com` a real AAYNA homepage, Privacy
Policy and Terms of Service so Google can review the OAuth branding. It is not
the shop.

- Pure HTML and CSS. No JavaScript, no forms, no API, no database, no
  environment variables, no cookies, no analytics, no third-party requests.
- Fonts (Playfair Display, DM Sans; SIL OFL) are self-hosted in `fonts/`.
- `vercel.json`: clean URLs (`/privacy`, `/terms`), a strict
  Content-Security-Policy (`script-src 'none'`), HSTS, nosniff, DENY framing.
- Every other path (for example `/admin`, `/account`, `/api/...`) returns the
  static `404.html`. There is nothing behind it.

Pages: `/` (index.html), `/privacy`, `/terms`, plus `robots.txt` and
`sitemap.xml` that point to https://shopaayna.com.

## Hosting

Deployed as its own Vercel project, **aayna-public**, separate from the
`aayna-webapp` ecommerce project. It has no Git connection and no environment
variables, so it cannot reach `aayna_prod` or any secret. Deployment
Protection stays on for its `*.vercel.app` URLs; only a custom domain that the
founder attaches is public.

At launch, remove `shopaayna.com` from aayna-public and add it to
aayna-webapp. Move the Privacy/Terms wording into
`frontend/src/data/staticPages.js` so the shop serves the same `/privacy`
and `/terms` URLs that the Google OAuth branding uses.

## Local check

    python3 -m http.server -d brand-site 8080   # cleanUrls are not emulated; open /privacy.html

## Founder review before or after Google review

Policy wording uses only facts from the app's code and founder-approved
policies. The items below are flagged and were not invented:

1. Legal entity name and registered address: not stated (none confirmed for public use).
2. Retention: no fixed periods are stated, and account deletion has no promised timeline.
3. The courier is named only as "our courier partner". Vercel, MongoDB Atlas and Resend are named as processors because the app uses them.
4. The terms add standard clauses not covered by earlier policy text: order acceptance on confirmation, account suspension for fraud/misuse, and site content ownership.
5. Exchanges/returns: no exchange window or refund promise is offered (founder decision, 20 Oct). Terms only say to email AAYNA about a damaged or incorrect order, and that the policy will be published before the shop opens. Note: the shop's own `frontend/src/data/staticPages.js` still has a 7-day returns page; update it before launch.
6. Not included until decided: governing law, limitation of liability, warranties, delivery time promises, refund method and timing.
7. If analytics or new payment methods are enabled, update the Privacy Policy first.

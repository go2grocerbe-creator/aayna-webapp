# AAYNA — Production Standard

This document defines the only acceptance criteria for the clean release. The application remains AAYNA, operated under Vellora Mercantile International. Hosting provider is intentionally undecided. Historic demo/meeting and blank-screen hotfixes are not release specifications.

## Keep
- Customer storefront: home, catalog/category, product details, cart, checkout/order request, delivery/returns/contact and policy pages.
- Actual product data, assets and brand tokens where verified.
- Authenticated admin for product, stock and order management.
- Backend/API/database integrations required for real orders.
- SEO metadata, canonical pages, sitemap/robots and analytics only where implemented and validated.

## Responsive release matrix
Run browser checks at 320, 360, 375, 390, 430, 768, 820, 1024, 1280, 1440 and 1920 CSS pixels. Include iOS Safari and Android Chrome, touch input, and tablet portrait/landscape.

Pass criteria at **every** viewport:
- document.scrollWidth <= document.clientWidth; no clipped headings, cropped product actions or unintended scroll containers.
- navigable responsive header, menu, categories, product grid, cart, checkout and footer.
- tap targets approximately 44 CSS px; no hover-only product/category action.
- readable typography, stable image aspect ratios, no header overlap, no sticky element hiding CTAs.
- all prices in BDT; product availability and variant/quantity selection behave correctly.
- actionable validation errors, loading/empty/error states; keyboard focus visible.
- usable forms with mobile keyboards, shipping/address fields and order confirmation.
- no request failures, uncaught browser errors or console errors in production paths.

## Security/data
- Public endpoints never include supplier costs, purchase costs, internal notes, margins, admin JWTs or secrets.
- Admin auth and role permissions enforced server-side; no default production credentials.
- No fake/demo products in production. Customer phone/address/order records restricted to authorized operations.
- Production configuration and secrets outside Git.

## Release gates
1. Inspect current application routing and existing components. Choose one real storefront; remove unused showcases only after feature parity.
2. Restore all major journeys and backend error handling before styling.
3. Fix layout and interactions against the responsive matrix with screenshot evidence.
4. Execute clean installs, build, unit/integration tests, API security checks, and a complete test order.
5. Confirm SEO, accessibility and performance budgets on mobile.
6. Deploy to a staging target independent of hosting brand; publish only on explicit release approval.

No forced history rewrite or deletion of historical commits is required to remove obsolete code from the active release.

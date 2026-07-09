\---

description: Use to audit AAYNA Webapp for public/private data leaks, admin auth, customer privacy, secrets, XSS, CORS, JWT, and SEO noindex issues.

\---



Audit:

\- backend/server.py

\- backend/admin\_routes.py

\- backend/auth.py

\- backend/storage.py

\- backend/db.py

\- frontend public product pages

\- frontend admin pages

\- product API responses

\- order/customer API responses

\- environment handling

\- robots/noindex behavior



Must not expose publicly:

\- supplier\_url

\- supplier\_price

\- cost\_price

\- landed\_cost

\- purchase\_cost

\- margin

\- internal\_notes

\- sourcing notes

\- private scoring notes

\- customer phone/address/order details



Security checks:

\- Admin routes require backend auth.

\- Role checks happen server-side.

\- JWT secrets are env-only.

\- Passwords are hashed.

\- CORS is not wide open for production.

\- Public APIs return only public fields.

\- Admin pages are noindex.

\- User/admin text is safely rendered against XSS.



Output:

1\. Critical issues

2\. High issues

3\. Medium issues

4\. Exact files/routes involved

5\. Suggested fix

6\. Test steps


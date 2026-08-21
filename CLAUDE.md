\# AAYNA Webapp Repo Rules



This repo is the AAYNA customer-facing ecommerce website and admin/order system.



Repo path:

E:\\deMarkt\\aayna-webapp\\Aayna-Webapp



GitHub remote:

https://github.com/go2grocerbe-creator/aayna-webapp.git



Related BuyOS/Product Scout repo:

E:\\deMarkt\\deMarkt\\aayna-product-scout-agent



Purpose:

\- Public ecommerce website for Bangladesh-focused women's accessories.

\- Product/category pages.

\- Cart/order flow.

\- Admin product/order management.

\- SEO and launch readiness.



Stack:

\- backend/ = Python backend with server.py, admin\_routes.py, auth.py, db.py, storage.py.

\- frontend/ = React/CRACO/Tailwind frontend.

\- tests/ = project tests.

\- memory/ = previous project/build memory.



This repo must never publicly expose internal BuyOS fields:

\- supplier\_url

\- supplier\_price

\- cost\_price

\- landed\_cost

\- purchase\_cost

\- margin

\- internal\_notes

\- sourcing notes

\- private scoring notes



Allowed public product fields:

\- sku

\- title

\- slug

\- category

\- public\_price\_bdt

\- compare\_at\_price\_bdt

\- images

\- public\_description

\- material

\- care\_note

\- stock\_status

\- approved\_public

\- seo\_title

\- seo\_description



Security rules:

\- Admin routes require backend authentication and authorization.

\- Customer phone/address/order data is private.

\- JWT secrets/API keys must stay in environment variables.

\- Passwords must be hashed.

\- CORS must be restricted in production.

\- Admin/internal routes should be noindex.

\- Use fake data only in preview/testing.



MVP priority:

1\. Secure admin/product/order handling.

2\. Public product/category pages.

3\. Mobile-first shopping flow.

4\. SEO basics.

5\. Policies and launch readiness.

6\. Sanitized product import from BuyOS.



Do not build:

\- seller dashboard

\- partner brand onboarding

\- marketplace system

\- complex automation before launch



Never invent:

\- admin credentials

\- supplier fees

\- payment decisions

\- scoring weights

\- private GitHub links



Workflow:

1\. Inspect relevant files before editing.

2\. Make the smallest safe change.

3\. Separate MVP-now from later.

4\. Provide exact test steps.


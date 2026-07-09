\---

description: Use when connecting AAYNA BuyOS/Product Scout approved products to the Webapp public product catalog.

\---



Goal:

Design or review the sanitized product bridge from BuyOS to Webapp.



BuyOS internal repo:

E:\\deMarkt\\deMarkt\\aayna-product-scout-agent



Webapp repo:

E:\\deMarkt\\aayna-webapp\\Aayna-Webapp



Rules:

\- BuyOS may contain internal product intelligence.

\- Webapp receives only sanitized public product fields.

\- Never import supplier links, cost, landed cost, purchase cost, margin, internal notes, or private scoring notes into public Webapp data.



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



Before editing:

1\. Inspect BuyOS export format if available.

2\. Inspect Webapp product model/API.

3\. Identify field mismatch.

4\. Propose the smallest safe import path.

5\. Do not change scoring weights.

6\. Do not expose internal data.



Output:

1\. Current data flow

2\. Safe public schema

3\. Fields to exclude

4\. Exact files to change

5\. Test steps


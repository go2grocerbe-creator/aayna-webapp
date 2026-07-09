\---

description: Use when reviewing or changing AAYNA admin login, admin dashboard, product management, order management, auth, roles, or temporary test admin setup.

\---



Admin rules:

\- Do not invent admin credentials.

\- Do not hardcode production admin email/password.

\- Temporary preview admins must use fake/test data only.

\- Passwords must be hashed.

\- JWT secrets must be env-only.

\- Admin APIs require backend authentication and authorization.

\- Admin UI hiding is not enough; backend must enforce access.

\- Admin pages should be noindex.



Check files likely involved:

\- backend/admin\_routes.py

\- backend/auth.py

\- backend/server.py

\- backend/seed\_data.py

\- frontend/src admin routes/pages/components

\- .env.example

\- README.md



Output:

1\. Current admin route/login flow

2\. How admin users are created

3\. Credential/security risks

4\. Exact fixes needed

5\. Test steps


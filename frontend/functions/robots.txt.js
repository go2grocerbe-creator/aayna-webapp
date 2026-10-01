// Cloudflare Pages Function: serve /robots.txt from the backend, which renders it
// from live catalogue data (backend/server.py). Without this, Pages' SPA
// fallback would answer /robots.txt with index.html.
export async function onRequestGet({ env }) {
  const api = (env.REACT_APP_BACKEND_URL || "").replace(/\/$/, "");
  if (!api) return new Response("Backend URL not configured", { status: 503 });
  const res = await fetch(`${api}/robots.txt`, { cf: { cacheTtl: 3600, cacheEverything: true } });
  return new Response(res.body, {
    status: res.status,
    headers: { "Content-Type": res.headers.get("Content-Type") || "text/plain; charset=utf-8",
               "Cache-Control": "public, max-age=3600" },
  });
}

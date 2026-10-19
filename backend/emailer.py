"""
AAYNA transactional email engine (Resend).

One place that renders and sends every customer email. Callers ask for an
event ("verify_email", "order_confirmation", ...) and get back an honest result:
`sent` only when Resend accepted the message. Nothing here ever raises into the
caller - order placement and account flows decide what a failure means.

Configuration (environment only, never the frontend):
    RESEND_API_KEY        sending-only key. Missing -> every send is recorded as
                          "not_configured" (never reported as sent).
    EMAIL_MODE            "resend" (default when a key is set) | "capture"
                          (tests/local: messages are kept in memory, nothing leaves
                          the process; refused in production).
    EMAIL_FROM_ACCOUNTS   default "AAYNA Accounts <accounts@shopaayna.com>"
    EMAIL_FROM_ORDERS     default "AAYNA Orders <orders@shopaayna.com>"
    EMAIL_REPLY_TO        default "shopaayna.bd@gmail.com"
    SUPPORT_CONTACT       shown in footers; default the Reply-To address

What is stored (collection email_logs): event, template, masked recipient,
dedupe key, status, provider message id, attempt count, error class/HTTP status.
Never stored or logged: the API key, message bodies, links or tokens.
"""
import asyncio
import hashlib
import html
import logging
import os
import uuid
from typing import Optional

import httpx
from pymongo.errors import DuplicateKeyError

from db import db, now_iso

logger = logging.getLogger("aayna.email")

RESEND_URL = "https://api.resend.com/emails"
DEFAULT_FROM_ACCOUNTS = "AAYNA Accounts <accounts@shopaayna.com>"
DEFAULT_FROM_ORDERS = "AAYNA Orders <orders@shopaayna.com>"
DEFAULT_REPLY_TO = "shopaayna.bd@gmail.com"
MAX_ATTEMPTS = 3
TIMEOUT_SECONDS = 8

# In "capture" mode (tests / local QA only) rendered messages land here instead
# of being sent, so automated tests can follow real links end to end.
CAPTURED: list = []


def _env(name, default=""):
    return (os.environ.get(name) or default).strip()


def _is_production() -> bool:
    return _env("APP_ENV", "development").lower() in ("production", "prod")


def email_mode() -> str:
    mode = _env("EMAIL_MODE").lower()
    if mode == "capture" and not _is_production():
        return "capture"
    return "resend"


def is_configured() -> bool:
    return email_mode() == "capture" or bool(_env("RESEND_API_KEY"))


def mask_email(addr: str) -> str:
    a = (addr or "").strip()
    if "@" not in a:
        return "?"
    user, dom = a.split("@", 1)
    return (user[:2] + "***@" + dom) if user else "***@" + dom


def _site_url() -> str:
    return _env("PUBLIC_SITE_URL", "http://localhost:3000").rstrip("/")


def site_base() -> str:
    """The public site origin with no preview access code (OAuth redirect URIs)."""
    return _site_url()


def _support() -> str:
    return _env("SUPPORT_CONTACT") or _env("EMAIL_REPLY_TO", DEFAULT_REPLY_TO)


# ---------------------------------------------------------------------------
# Templates: brand-consistent, single action, plain-text alternative.
# All dynamic values are HTML-escaped. Links are built by the backend only.
# ---------------------------------------------------------------------------
BURGUNDY = "#5c1a2b"
CREAM = "#f7f1ea"
CHARCOAL = "#2b2523"
TAUPE = "#7a6e66"


def _layout(title: str, intro_html: str, action_label: Optional[str], action_url: Optional[str],
            after_html: str, footer_reason: str) -> str:
    button = ""
    if action_label and action_url:
        button = (
            f'<tr><td style="padding:8px 0 24px"><a href="{html.escape(action_url, quote=True)}" '
            f'style="display:inline-block;background:{BURGUNDY};color:#ffffff;text-decoration:none;'
            f'font-weight:600;padding:14px 28px;font-family:Arial,Helvetica,sans-serif;font-size:15px">'
            f'{html.escape(action_label)}</a></td></tr>'
            f'<tr><td style="font-size:12px;color:{TAUPE};padding-bottom:20px;word-break:break-all">'
            f'If the button does not work, copy this link into your browser:<br>'
            f'<span style="color:{CHARCOAL}">{html.escape(action_url)}</span></td></tr>'
        )
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="color-scheme" content="light"><title>{html.escape(title)}</title></head>
<body style="margin:0;padding:0;background:{CREAM}">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:{CREAM}"><tr><td align="center" style="padding:32px 16px">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="max-width:560px;background:#ffffff;font-family:Arial,Helvetica,sans-serif;color:{CHARCOAL}">
<tr><td style="padding:28px 32px 8px;border-bottom:1px solid #eadfd4">
<div style="font-family:Georgia,'Times New Roman',serif;font-size:26px;letter-spacing:4px;color:{BURGUNDY};font-weight:bold">AAYNA</div></td></tr>
<tr><td style="padding:24px 32px 8px">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0">
<tr><td style="font-family:Georgia,'Times New Roman',serif;font-size:22px;color:{CHARCOAL};padding-bottom:14px">{html.escape(title)}</td></tr>
<tr><td style="font-size:15px;line-height:1.6;padding-bottom:16px">{intro_html}</td></tr>
{button}
<tr><td style="font-size:14px;line-height:1.6;color:{CHARCOAL}">{after_html}</td></tr>
</table></td></tr>
<tr><td style="padding:20px 32px 28px;font-size:12px;line-height:1.6;color:{TAUPE};border-top:1px solid #eadfd4">
{html.escape(footer_reason)}<br>Questions? Reply to this email or write to {html.escape(_support())}.<br>AAYNA &middot; Bangladesh</td></tr>
</table></td></tr></table></body></html>"""


def _text(title, intro, action_label, action_url, after, footer_reason):
    parts = ["AAYNA", "", title, "", intro]
    if action_label and action_url:
        parts += ["", f"{action_label}: {action_url}"]
    if after:
        parts += ["", after]
    parts += ["", "--", footer_reason, f"Questions? Reply to this email or write to {_support()}."]
    return "\n".join(parts)


def _money(n) -> str:
    try:
        return "৳" + f"{float(n):,.0f}"
    except (TypeError, ValueError):
        return "৳0"


def render(template: str, ctx: dict) -> dict:
    """Return {subject, html, text, sender} for a template. Raises KeyError on unknown templates."""
    name = html.escape(ctx.get("name") or "there")
    plain_name = ctx.get("name") or "there"
    if template in ("verify_email", "resend_verification"):
        title = "Confirm your email address"
        intro_t = f"Hi {plain_name}, please confirm this email address to activate your AAYNA account."
        intro_h = f"Hi {name}, please confirm this email address to activate your AAYNA account."
        after = f"This link expires in {ctx['expires_hours']} hours and can be used once."
        reason = "You received this because someone created an AAYNA account with this email address. If that wasn't you, you can ignore this email - no account will be activated."
        return {"subject": "Confirm your AAYNA account", "sender": "accounts",
                "html": _layout(title, intro_h, "Confirm email", ctx["url"], html.escape(after), reason),
                "text": _text(title, intro_t, "Confirm email", ctx["url"], after, reason)}
    if template == "account_exists":
        title = "You already have an AAYNA account"
        how = "Continue with Google" if ctx.get("google_only") else "sign in with your password, or reset it if you've forgotten it"
        intro_t = f"Someone tried to create a new AAYNA account with this email address, but an account already exists. To get in, {how}."
        reason = "You received this because a sign-up was attempted with this email address. If that wasn't you, no action is needed - your account is unchanged."
        return {"subject": "Your AAYNA account", "sender": "accounts",
                "html": _layout(title, html.escape(intro_t), "Go to sign in", ctx["url"], "", reason),
                "text": _text(title, intro_t, "Go to sign in", ctx["url"], "", reason)}
    if template == "password_reset":
        title = "Reset your password"
        intro_t = f"Hi {plain_name}, we received a request to reset the password for your AAYNA account."
        intro_h = f"Hi {name}, we received a request to reset the password for your AAYNA account."
        after = f"This link expires in {ctx['expires_minutes']} minutes and can be used once. Your current password keeps working until you choose a new one."
        reason = "You received this because a password reset was requested for this email address. If that wasn't you, ignore this email - your password will not change."
        return {"subject": "Reset your AAYNA password", "sender": "accounts",
                "html": _layout(title, intro_h, "Choose a new password", ctx["url"], html.escape(after), reason),
                "text": _text(title, intro_t, "Choose a new password", ctx["url"], after, reason)}
    if template == "password_changed":
        title = "Your password was changed"
        intro_t = f"Hi {plain_name}, the password for your AAYNA account was just changed and you were signed out of your other devices."
        intro_h = html.escape(intro_t)
        after = "If you did not make this change, reset your password straight away and contact us."
        reason = "This is a security notice about your AAYNA account."
        return {"subject": "Your AAYNA password was changed", "sender": "accounts",
                "html": _layout(title, intro_h, "Sign in", ctx["url"], html.escape(after), reason),
                "text": _text(title, intro_t, "Sign in", ctx["url"], after, reason)}
    if template == "email_change":
        title = "Confirm your new email address"
        intro_t = f"Hi {plain_name}, please confirm that you want to use this address for your AAYNA account."
        after = f"This link expires in {ctx['expires_hours']} hours. Until you confirm, your account keeps its current email address."
        reason = "You received this because an email change was requested on an AAYNA account. If that wasn't you, ignore this email."
        return {"subject": "Confirm your new AAYNA email", "sender": "accounts",
                "html": _layout(title, html.escape(intro_t), "Confirm new email", ctx["url"], html.escape(after), reason),
                "text": _text(title, intro_t, "Confirm new email", ctx["url"], after, reason)}
    if template == "order_claim":
        title = f"Add order {ctx['order_number']} to your account"
        intro_t = f"Hi {plain_name}, confirm that order {ctx['order_number']} is yours to see it in your AAYNA account."
        after = f"This link expires in {ctx['expires_hours']} hours."
        reason = "You received this because someone asked to add this order to an AAYNA account. If that wasn't you, ignore this email - nothing changes."
        return {"subject": f"Confirm order {ctx['order_number']}", "sender": "accounts",
                "html": _layout(title, html.escape(intro_t), "Add order to my account", ctx["url"], html.escape(after), reason),
                "text": _text(title, intro_t, "Add order to my account", ctx["url"], after, reason)}
    if template == "order_confirmation":
        o = ctx["order"]
        rows_h = "".join(
            f'<tr><td style="padding:4px 0">{html.escape(it["product_name_snapshot"])} &times; {int(it["quantity"])}</td>'
            f'<td align="right" style="padding:4px 0">{_money(it["total_price"])}</td></tr>' for it in o["items"])
        rows_t = "\n".join(f'- {it["product_name_snapshot"]} x{int(it["quantity"])}: {_money(it["total_price"])}' for it in o["items"])
        disc = float(o.get("discount_amount") or 0)
        totals = [("Subtotal", o["subtotal"])] + ([("Discount" + (f' ({o.get("coupon_code")})' if o.get("coupon_code") else ""), -disc)] if disc else []) \
            + [("Delivery", "Free" if o.get("free_delivery") and not float(o.get("delivery_charge") or 0) else o["delivery_charge"]),
               ("Total", o["total_amount"])]
        _amt = lambda v: v if isinstance(v, str) else f'{"-" if v < 0 else ""}{_money(abs(v))}'
        tot_h = "".join(f'<tr><td style="padding:2px 0;color:{TAUPE}">{html.escape(k)}</td><td align="right">{html.escape(_amt(v))}</td></tr>' for k, v in totals)
        tot_t = "\n".join(f'{k}: {_amt(v)}' for k, v in totals)
        title = f"Thank you - order {o['order_number']} received"
        intro_t = f"Hi {plain_name}, we've received your order. Our team will contact you to confirm it."
        table = f'<table role="presentation" width="100%" style="font-size:14px;border-top:1px solid #eadfd4;border-bottom:1px solid #eadfd4;margin:4px 0 12px">{rows_h}</table><table role="presentation" width="100%" style="font-size:14px">{tot_h}</table><p style="font-size:14px">Payment: {html.escape(o["payment_method"])}</p>'
        reason = "You received this because an order was placed on AAYNA with this email address."
        return {"subject": f"AAYNA order {o['order_number']} received", "sender": "orders",
                "html": _layout(title, html.escape(intro_t), "Track your order", ctx["url"], table, reason),
                "text": _text(title, intro_t, "Track your order", ctx["url"], rows_t + "\n\n" + tot_t + f"\nPayment: {o['payment_method']}", reason)}
    if template == "order_status":
        o = ctx["order"]
        label = ctx["label"]
        title = f"Order {o['order_number']}: {label}"
        intro_t = f"Hi {plain_name}, your AAYNA order {o['order_number']} is now: {label}."
        extra = ""
        if o.get("courier_name"):
            extra = f"Courier: {o['courier_name']}" + (f" - tracking reference {o['courier_tracking_code']}" if o.get("courier_tracking_code") else "")
        reason = "You received this because you placed an order on AAYNA with this email address."
        return {"subject": f"AAYNA order {o['order_number']}: {label}", "sender": "orders",
                "html": _layout(title, html.escape(intro_t), "View your order", ctx["url"], html.escape(extra), reason),
                "text": _text(title, intro_t, "View your order", ctx["url"], extra, reason)}
    raise KeyError(template)


def _sender(kind: str) -> str:
    if kind == "orders":
        return _env("EMAIL_FROM_ORDERS", DEFAULT_FROM_ORDERS)
    return _env("EMAIL_FROM_ACCOUNTS", DEFAULT_FROM_ACCOUNTS)


async def _post_resend(payload: dict, idempotency_key: str):
    """Returns (status, provider_id, error). Bounded retries on 429/5xx/network."""
    key = _env("RESEND_API_KEY")
    headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json",
               "User-Agent": "aayna-webapp/1.0", "Idempotency-Key": idempotency_key[:256]}
    last_err = None
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            async with httpx.AsyncClient(timeout=TIMEOUT_SECONDS) as cli:
                resp = await cli.post(RESEND_URL, json=payload, headers=headers)
            if resp.status_code in (200, 201):
                return "sent", (resp.json() or {}).get("id"), None, attempt
            # Only the provider's error *name* and status are kept - never the body.
            try:
                name = (resp.json() or {}).get("name") or ""
            except ValueError:
                name = ""
            last_err = f"HTTP {resp.status_code} {name}".strip()
            if resp.status_code not in (429, 500, 502, 503, 504):
                return "failed", None, last_err, attempt
        except Exception as exc:  # noqa: BLE001
            last_err = f"network: {type(exc).__name__}"
        if attempt < MAX_ATTEMPTS:
            await asyncio.sleep(0.6 * attempt)
    return "failed", None, last_err, MAX_ATTEMPTS


async def send(event: str, template: str, to: str, ctx: dict, dedupe_key: Optional[str] = None,
               account_id: Optional[str] = None, order_number: Optional[str] = None) -> dict:
    """Render and send one email. Returns {"status": sent|failed|not_configured|duplicate, "log_id": ...}.
    With a dedupe_key, the same logical message is sent at most once (a second call
    returns "duplicate" without contacting the provider)."""
    to = (to or "").strip()
    log = {
        "id": str(uuid.uuid4()), "event": event, "template": template,
        "to_masked": mask_email(to), "to_hash": hashlib.sha256(to.lower().encode()).hexdigest() if to else None,
        "account_id": account_id, "order_number": order_number,
        "dedupe_key": dedupe_key, "status": "pending", "provider_id": None,
        "attempts": 0, "error": None, "mode": email_mode(), "created_at": now_iso(), "updated_at": now_iso(),
    }
    if dedupe_key:
        try:
            await db.email_dedupe.insert_one({"_id": dedupe_key, "log_id": log["id"], "created_at": now_iso()})
        except DuplicateKeyError:
            return {"status": "duplicate", "log_id": None}
    if not to or "@" not in to:
        log.update(status="failed", error="no recipient")
        await db.email_logs.insert_one({**log})
        return {"status": "failed", "log_id": log["id"]}
    try:
        msg = render(template, ctx)
    except Exception as exc:  # noqa: BLE001
        log.update(status="failed", error=f"render: {type(exc).__name__}")
        await db.email_logs.insert_one({**log})
        return {"status": "failed", "log_id": log["id"]}

    mode = email_mode()
    if mode == "capture":
        CAPTURED.append({"to": to, "event": event, "template": template, "subject": msg["subject"],
                         "html": msg["html"], "text": msg["text"], "from": _sender(msg["sender"])})
        capture_file = _env("EMAIL_CAPTURE_FILE")
        if capture_file:  # local browser tests follow real links; capture mode never runs in production
            import json
            with open(capture_file, "a", encoding="utf-8") as fh:
                fh.write(json.dumps({"to": to, "template": template, "subject": msg["subject"], "text": msg["text"],
                                     "from": _sender(msg["sender"])}) + "\n")
        log.update(status="sent", provider_id="captured-" + log["id"][:8], attempts=1)
    elif not _env("RESEND_API_KEY"):
        log.update(status="not_configured", error="RESEND_API_KEY not set")
        logger.warning("Email %s to %s not sent: email is not configured", event, log["to_masked"])
    else:
        payload = {"from": _sender(msg["sender"]), "to": [to],
                   "reply_to": _env("EMAIL_REPLY_TO", DEFAULT_REPLY_TO),
                   "subject": msg["subject"], "html": msg["html"], "text": msg["text"],
                   "tags": [{"name": "event", "value": event}]}
        status, pid, err, attempts = await _post_resend(payload, dedupe_key or log["id"])
        log.update(status=status, provider_id=pid, error=err, attempts=attempts)
        if status != "sent":
            logger.warning("Email %s to %s failed: %s", event, log["to_masked"], err)
    log["updated_at"] = now_iso()
    await db.email_logs.insert_one({**log})
    if log["status"] != "sent" and dedupe_key:
        # A failed attempt must not block a later legitimate retry of the same message.
        await db.email_dedupe.delete_one({"_id": dedupe_key, "log_id": log["id"]})
    return {"status": log["status"], "log_id": log["id"]}


_PREVIEW_ACCESS_RE = __import__("re").compile(r"^_vercel_share=[A-Za-z0-9]{16,64}$")


def _preview_access_query() -> str:
    """TEST PREVIEWS ONLY. Vercel Deployment Protection sends anyone without a
    Vercel login to vercel.com/login, so email links on a protected preview
    cannot reach the app. EMAIL_LINK_PREVIEW_ACCESS may hold a temporary,
    deployment-scoped Vercel shareable-link code ("_vercel_share=...") that is
    appended to links in emails. It is ignored unless the site is a
    *.vercel.app preview address, so it can never affect a real domain."""
    q = _env("EMAIL_LINK_PREVIEW_ACCESS")
    host = _site_url().split("://", 1)[-1].split("/", 1)[0].lower()
    if not q or not host.endswith(".vercel.app") or not _PREVIEW_ACCESS_RE.match(q):
        return ""
    return q


def site_link(path: str) -> str:
    """Absolute link into the site. A #fragment (where one-time tokens live)
    always stays last, after any query string."""
    access = _preview_access_query()
    if not access:
        return _site_url() + path
    base, sep, frag = path.partition("#")
    base += ("&" if "?" in base else "?") + access
    return _site_url() + base + (sep + frag if sep else "")

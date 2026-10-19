"""
Product description content (Admin -> Products -> Description & details).

Plain text only. The storefront renders these fields as text (React escapes it),
and the server also refuses anything that looks like markup, so no HTML or script
can be stored or served. Bengali and other Unicode text is accepted (NFC-normalised).

Fields (all optional; empty = not shown on the storefront):
    short_description   one or two sentences under the product name (<= 300)
    full_description    the main description; blank lines separate paragraphs (<= 3,000)
    highlights          up to 6 short product-detail lines (<= 120 each)
    material            only when verified (<= 120)              [existing field]
    size                dimensions / size information (<= 120)    [existing field]
    care_note           care instructions, only when verified (<= 500)
    seo_title           search-result title (<= 70)
    seo_description     search-result description (<= 170)

Every change is recorded in product_content_history (who, when, field, before, after).
"""
import re
import unicodedata
import uuid
from typing import Optional

from fastapi import HTTPException

LIMITS = {"short_description": 300, "full_description": 3000, "material": 120, "size": 120,
          "care_note": 500, "seo_title": 70, "seo_description": 170}
HIGHLIGHTS_MAX, HIGHLIGHT_LEN = 6, 120
TEXT_FIELDS = tuple(LIMITS)
CONTENT_FIELDS = TEXT_FIELDS + ("highlights",)
SINGLE_LINE = {"material", "size", "seo_title", "seo_description"}
LABELS = {"short_description": "Short description", "full_description": "Description", "material": "Material",
          "size": "Size / dimensions", "care_note": "Care", "seo_title": "SEO title", "seo_description": "SEO description",
          "highlights": "Product details"}

MARKUP = re.compile(r"<\s*/?\s*[a-zA-Z!?][^>]*>|javascript\s*:|on[a-z]+\s*=\s*[\"']", re.I)
CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f​-‏‪-‮⁦-⁩]")


def clean_text(field: str, value, single_line: bool = False) -> str:
    label = LABELS.get(field, field)
    if value is None:
        return ""
    if not isinstance(value, str):
        raise HTTPException(status_code=400, detail=f"{label} must be text")
    v = unicodedata.normalize("NFC", value).replace("\r\n", "\n").replace("\r", "\n").replace("\t", " ")
    v = CONTROL.sub("", v)
    if MARKUP.search(v):
        raise HTTPException(status_code=400, detail=f"{label}: plain text only - HTML, scripts and links in markup are not allowed")
    if single_line:
        v = re.sub(r"\s+", " ", v)
    else:
        v = "\n".join(re.sub(r"[ ]{2,}", " ", line).strip() for line in v.split("\n"))
        v = re.sub(r"\n{3,}", "\n\n", v)
    return v.strip()


def normalize_content(data: dict) -> dict:
    """Validate and clean whichever content fields are present in `data`. Raises 400."""
    out = {}
    for f in TEXT_FIELDS:
        if f in data:
            v = clean_text(f, data[f], single_line=f in SINGLE_LINE)
            if len(v) > LIMITS[f]:
                raise HTTPException(status_code=400, detail=f"{LABELS[f]} is too long ({len(v)} characters, maximum {LIMITS[f]})")
            out[f] = v
    if "highlights" in data:
        hs = data["highlights"]
        if hs is None:
            hs = []
        if not isinstance(hs, list):
            raise HTTPException(status_code=400, detail="Product details must be a list of short lines")
        cleaned = [clean_text("highlights", h, single_line=True) for h in hs]
        cleaned = [h for h in cleaned if h]
        if len(cleaned) > HIGHLIGHTS_MAX:
            raise HTTPException(status_code=400, detail=f"At most {HIGHLIGHTS_MAX} product-detail lines")
        for h in cleaned:
            if len(h) > HIGHLIGHT_LEN:
                raise HTTPException(status_code=400, detail=f"Each product-detail line can have at most {HIGHLIGHT_LEN} characters")
        out["highlights"] = cleaned
    return out


def completeness(p: dict) -> dict:
    """complete = short + main description written; partial = one of them; missing = neither."""
    short = bool((p.get("short_description") or "").strip())
    full = bool((p.get("full_description") or "").strip())
    status = "complete" if short and full else ("partial" if short or full else "missing")
    optional = [f for f in ("highlights", "material", "care_note", "seo_title", "seo_description") if p.get(f)]
    return {"status": status, "short": short, "full": full, "optional_filled": optional}


async def record_changes(db, product: dict, new_values: dict, actor: Optional[str], when: str):
    changes = {}
    for f in CONTENT_FIELDS:
        if f in new_values:
            before = product.get(f) if product.get(f) is not None else ([] if f == "highlights" else "")
            if new_values[f] != before:
                changes[f] = {"from": before, "to": new_values[f]}
    if changes:
        await db.product_content_history.insert_one({"id": str(uuid.uuid4()), "product_id": product.get("id"), "sku": product.get("sku"),
                                                     "actor": actor, "changes": changes, "created_at": when})
    return changes


def seo_description_fallback(p: dict) -> str:
    """Meta description: the founder's SEO text, else the short description, else a factual line."""
    if p.get("seo_description"):
        return p["seo_description"]
    if p.get("short_description"):
        return p["short_description"][:170]
    return ""

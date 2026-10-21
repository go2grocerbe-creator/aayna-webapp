"""AAYNA gallery contract, importable without FastAPI/Mongo dependencies.

Use as invariant/validation module; integrate with backend's existing product API,
role permissions, audit trail and static galleries. No database access here.
"""
from __future__ import annotations
import hashlib
import re
from urllib.parse import urlparse

MAX_IMAGES = 20
MAX_ALT = 180
LOCAL_PREFIX = "/product-images/"
SKU = re.compile(r"^[A-Z0-9-]{5,48}$")

class GalleryError(ValueError):
    pass

def stable_id(url: str) -> str:
    return "legacy_" + hashlib.sha256(url.encode("utf-8")).hexdigest()[:16]

def valid_url(url: str, public_hosts: tuple[str, ...] = ()) -> bool:
    if not isinstance(url, str) or len(url) > 2048 or "\\" in url:
        return False
    if url.startswith(LOCAL_PREFIX):
        return not any(x in url for x in ("..", "?", "#")) and "//" not in url[1:]
    parsed = urlparse(url)
    return parsed.scheme == "https" and parsed.hostname in public_hosts and parsed.username is None and parsed.password is None and not parsed.fragment

def normalize_legacy(urls: list[str], public_hosts: tuple[str, ...] = ()) -> list[dict]:
    """Existing static asset URLs remain intact and immutable; first is catalogue cover."""
    if len(urls) > MAX_IMAGES:
        raise GalleryError("too many images")
    out = []
    for idx, url in enumerate(urls):
        if not valid_url(url, public_hosts):
            raise GalleryError("unapproved gallery URL")
        out.append({"id":stable_id(url),"url":url,"source":"static","alt":"","position":idx})
    return out

def validate_gallery(images: list[dict], public_hosts: tuple[str, ...] = ()) -> list[dict]:
    """Return canonical ordered gallery. Caller handles DB CAS and permissions."""
    if not isinstance(images, list) or len(images) > MAX_IMAGES:
        raise GalleryError("gallery must be a list of up to 20 images")
    ids=set(); urls=set(); result=[]
    for i, image in enumerate(images):
        if not isinstance(image,dict): raise GalleryError("invalid image")
        image_id=image.get("id"); url=image.get("url")
        if not isinstance(image_id,str) or not re.fullmatch(r"[A-Za-z0-9_-]{6,80}", image_id):
            raise GalleryError("invalid image id")
        if image_id in ids or url in urls: raise GalleryError("duplicate image")
        if not valid_url(url,public_hosts): raise GalleryError("unapproved image URL")
        if image.get("source") not in ("static","r2"): raise GalleryError("invalid image source")
        alt=image.get("alt","")
        if not isinstance(alt,str) or len(alt)>MAX_ALT or "<" in alt or ">" in alt:
            raise GalleryError("invalid alt text")
        ids.add(image_id);urls.add(url)
        result.append({"id":image_id,"url":url,"source":image["source"],"alt":alt.strip(),"position":i})
    return result

def apply_order(existing: list[dict], ordered_ids: list[str], public_hosts: tuple[str, ...] = ()) -> list[dict]:
    """No lost/added images; reorder is an exact permutation, not an upsert."""
    if len(existing)!=len(ordered_ids) or len(set(ordered_ids))!=len(ordered_ids):
        raise GalleryError("order must include each current image exactly once")
    lookup={i["id"]:i for i in existing}
    if set(ordered_ids)!=set(lookup): raise GalleryError("gallery changed; reload before saving")
    return validate_gallery([lookup[i] for i in ordered_ids], public_hosts)

def image_cover(images:list[dict]) -> str | None:
    return images[0]["url"] if images else None

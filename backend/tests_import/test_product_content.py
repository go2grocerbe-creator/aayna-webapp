"""Product description management: validation, sanitising, permissions, visibility, history."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_customer_accounts import env, client, admin_h, run  # noqa: E402,F401


def put(env, pid, body, role="super_admin"):
    return client().put(f"/api/admin/products/{pid}", headers=admin_h(env, role), json=body)


def test_write_edit_clear_description_keeps_draft_and_records_history(env):
    run(env["db"].products.update_one({"id": "p1"}, {"$set": {"status": "draft"}}))
    body = {"short_description": "  A bold ring with a polished golden finish.  ",
            "full_description": "First paragraph.\r\n\r\n\r\nSecond   paragraph\twith tab.",
            "highlights": ["Sold individually", "", "  Open band  "], "care_note": "",
            "seo_title": "Classic Statement Ring", "seo_description": "Golden statement ring from AAYNA."}
    r = put(env, "p1", body)
    assert r.status_code == 200, r.text
    p = r.json()
    assert p["status"] == "draft"  # saving content never publishes
    assert p["short_description"] == "A bold ring with a polished golden finish."
    assert p["full_description"] == "First paragraph.\n\nSecond paragraph with tab."
    assert p["highlights"] == ["Sold individually", "Open band"]
    assert p["content_status"]["status"] == "complete"
    hist = client().get("/api/admin/products/p1/content-history", headers=admin_h(env)).json()
    assert len(hist) == 1 and set(hist[0]["changes"]) >= {"short_description", "full_description", "highlights", "seo_title"}
    assert hist[0]["actor"] == "super_admin@example.test"
    # clear again -> missing, optional fields stay optional
    r = put(env, "p1", {"short_description": "", "full_description": "", "highlights": [], "seo_title": "", "seo_description": ""})
    assert r.json()["content_status"]["status"] == "missing" and r.json()["highlights"] == []
    # draft products are not public at all
    assert client().get("/api/products/prod-p1").status_code == 404


def test_public_api_exposes_content_only_for_public_products(env):
    put(env, "p2", {"short_description": "Pair of floral earrings.", "full_description": "Golden floral earrings.",
                    "highlights": ["Sold as a pair"], "material": "", "care_note": "Keep dry."})
    d = client().get("/api/products/prod-p2").json()["product"]
    assert d["short_description"] == "Pair of floral earrings." and d["highlights"] == ["Sold as a pair"] and d["care_note"] == "Keep dry."
    for private in ("cost_price", "internal_notes", "pricing", "price_history", "source", "content_status"):
        assert private not in d


def test_bengali_and_english_text(env):
    bn = "সোনালি রঙের ফুলেল কানের দুল। প্রতিদিন পরার জন্য।"
    r = put(env, "p2", {"short_description": bn, "full_description": "Golden floral earrings.\n\n" + bn, "highlights": ["জোড়ায় বিক্রি হয়"]})
    assert r.status_code == 200 and r.json()["short_description"] == bn and r.json()["highlights"] == ["জোড়ায় বিক্রি হয়"]
    assert client().get("/api/products/prod-p2").json()["product"]["short_description"] == bn


def test_markup_scripts_and_oversize_are_refused(env):
    for bad in ("<script>alert(1)</script>", "Nice <b>ring</b>", "<img src=x onerror=alert(1)>", "click javascript:alert(1)",
                "x\" onmouseover=\"alert(1)"):
        r = put(env, "p2", {"full_description": bad})
        assert r.status_code == 400, bad
    assert put(env, "p2", {"short_description": "x" * 301}).status_code == 400
    assert put(env, "p2", {"seo_title": "x" * 71}).status_code == 400
    assert put(env, "p2", {"highlights": ["a"] * 7}).status_code == 400
    assert put(env, "p2", {"highlights": ["x" * 121]}).status_code == 400
    assert put(env, "p2", {"highlights": "not a list"}).status_code in (400, 422)
    assert put(env, "p2", {"care_note": 5}).status_code in (400, 422)
    # zero-width / control characters are stripped, "<3" style text is fine
    r = put(env, "p2", {"short_description": "Love it <3​\u0007"})
    assert r.status_code == 200 and r.json()["short_description"] == "Love it <3"
    # nothing invalid was stored
    p = run(env["db"].products.find_one({"id": "p2"}))
    assert "<script" not in str(p) and "onerror" not in str(p)


def test_only_product_editors_can_change_descriptions(env):
    assert put(env, "p2", {"full_description": "x"}, role="order_manager").status_code == 403
    assert client().put("/api/admin/products/p2", json={"full_description": "x"}).status_code in (401, 403)
    assert put(env, "p2", {"full_description": "Edited by the product manager."}, role="product_manager").status_code == 200
    # product managers never see purchase costs while editing content
    r = client().get("/api/admin/products/p2", headers=admin_h(env, "product_manager")).json()
    assert "cost_price" not in r and r["content_status"]["status"] in ("partial", "complete")


def test_create_with_content_and_list_status(env):
    c = client()
    r = c.post("/api/admin/products", headers=admin_h(env), json={
        "product_name": "Test Hoops", "sku": "AYN-TST-HOOP", "category_slug": "earrings", "selling_price": 900, "stock_quantity": 2,
        "short_description": "Small golden hoops.", "highlights": ["Sold as a pair"], "seo_description": "Small golden hoops."})
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "draft" and r.json()["highlights"] == ["Sold as a pair"]
    lst = c.get("/api/admin/products", headers=admin_h(env)).json()
    hoop = next(p for p in lst if p["sku"] == "AYN-TST-HOOP")
    assert hoop["content_status"]["status"] == "partial"
    assert c.post("/api/admin/products", headers=admin_h(env), json={
        "product_name": "Bad", "sku": "AYN-TST-BAD", "category_slug": "earrings", "selling_price": 900, "stock_quantity": 1,
        "full_description": "<iframe src=//evil>"}).status_code == 400

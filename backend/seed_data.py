"""Seed data for AAYNA storefront (Milestone 1). Sourced from the client Excel + brand spec."""
import uuid
from datetime import datetime, timezone


def _iso():
    return datetime.now(timezone.utc).isoformat()


def _img(url, alt):
    return [{"image_url": url, "alt_text": alt, "is_main": True, "sort_order": 0}]


_BASE = "https://static.prod-images.emergentagent.com/jobs/eb037f34-a12d-4a9a-95b9-7a0c51c7ca66/images"

# ---------------------------------------------------------------------------
# Categories
# ---------------------------------------------------------------------------
SEED_CATEGORIES = [
    {
        "id": str(uuid.uuid4()), "name": "Earrings", "slug": "earrings", "sku_prefix": "EAR",
        "description": "Everyday, pearl, hoop, stud, and statement earrings.",
        "image_url": f"{_BASE}/988646babc8e7d32d1e6c7459c6375b9d09b9c7e38cb5e1b8379ea762c88993d.png",
        "parent_category_id": None, "status": "active", "sort_order": 1,
        "created_at": _iso(), "updated_at": _iso(),
    },
    {
        "id": str(uuid.uuid4()), "name": "Necklaces", "slug": "necklaces", "sku_prefix": "NEC",
        "description": "Pendant, layered, chain, and minimal necklaces.",
        "image_url": f"{_BASE}/1c5239ec70675f537e1850121ef96ab33a791cf92f1899e5c602d1ce40149abc.png",
        "parent_category_id": None, "status": "active", "sort_order": 2,
        "created_at": _iso(), "updated_at": _iso(),
    },
    {
        "id": str(uuid.uuid4()), "name": "Rings", "slug": "rings", "sku_prefix": "RNG",
        "description": "Adjustable rings, stack ring sets, stone rings.",
        "image_url": f"{_BASE}/9b7f5f18b0f331cead0de56ab256246f101a6fc481b80727a6789d15c5f1db6d.png",
        "parent_category_id": None, "status": "active", "sort_order": 3,
        "created_at": _iso(), "updated_at": _iso(),
    },
    {
        "id": str(uuid.uuid4()), "name": "Bracelets", "slug": "bracelets", "sku_prefix": "BRC",
        "description": "Charm bracelets, pearl bracelets, chain bracelets.",
        "image_url": f"{_BASE}/b744f8fae5f83d77bf46c63a59a582217c477e2704a6c8161d0c192c22c866ad.png",
        "parent_category_id": None, "status": "active", "sort_order": 4,
        "created_at": _iso(), "updated_at": _iso(),
    },
    {
        "id": str(uuid.uuid4()), "name": "Hair Accessories", "slug": "hair-accessories", "sku_prefix": "HAR",
        "description": "Scrunchies, clips, claw clips, hair bands.",
        "image_url": f"{_BASE}/aa205bf4ac92863bf75874286a0518d740c16417807c82aec89a269c1482e42a.png",
        "parent_category_id": None, "status": "active", "sort_order": 5,
        "created_at": _iso(), "updated_at": _iso(),
    },
    {
        "id": str(uuid.uuid4()), "name": "Gift Sets", "slug": "gift-sets", "sku_prefix": "GFT",
        "description": "Accessory bundles and gift-ready sets.",
        "image_url": f"{_BASE}/9a3d65ac423df05456897c46e624b7a4c5b8a3677c12d406959c899a03ed0a3f.png",
        "parent_category_id": None, "status": "active", "sort_order": 6,
        "created_at": _iso(), "updated_at": _iso(),
    },
]


def _product(name, slug, sku, cat_name, cat_slug, selling, discount, cost, stock,
             material, color, size, short, full, tags, featured, best, new, img_url, alt):
    return {
        "id": str(uuid.uuid4()),
        "product_name": name, "slug": slug, "sku": sku,
        "category_id": None, "category_name": cat_name, "category_slug": cat_slug,
        "brand_id": None, "seller_id": None,
        "short_description": short, "full_description": full,
        "cost_price": cost, "selling_price": selling, "discount_price": discount,
        "stock_quantity": stock, "low_stock_alert": 3,
        "material": material, "color": color, "size": size, "weight": None,
        "status": "active",
        "is_featured": featured, "is_best_seller": best, "is_new_arrival": new,
        "tags": [t.strip() for t in tags.split(",")],
        "images": _img(img_url, alt),
        "internal_notes": "",
        "created_at": _iso(), "updated_at": _iso(),
    }


# ---------------------------------------------------------------------------
# Products (from AAYNA_10_Product_Upload_Template.xlsx)
# ---------------------------------------------------------------------------
SEED_PRODUCTS = [
    _product(
        "Gold Pearl Hoop Earrings", "gold-pearl-hoop-earrings", "EAR-GD-0001", "Earrings", "earrings",
        450, 399, 160, 5, "Alloy with artificial pearl", "Gold and white", "Medium",
        "Elegant pearl hoop earrings for everyday and occasion wear.",
        "A lightweight pair of gold-tone hoop earrings with pearl detail. Perfect for casual outfits, parties, and gifting. Keep away from water and perfume for longer use.",
        "New Arrival, Gift Friendly, Pearl, Gold Tone, Everyday Wear", True, False, True,
        f"{_BASE}/3f804168c5b82c428307e69554e5d9f9a3adcc250c5de406f7d2d04fe9288423.png",
        "Gold pearl hoop earrings by AAYNA",
    ),
    _product(
        "Rose Quartz Drop Earrings", "rose-quartz-drop-earrings", "EAR-RS-0002", "Earrings", "earrings",
        520, 469, 190, 4, "Alloy with rose quartz-style stone", "Rose pink and gold", "Medium",
        "Soft rose drop earrings with a feminine stone-inspired finish.",
        "A romantic pair of rose quartz-style drop earrings designed for soft feminine outfits. Best for brunch, casual events, and gifting.",
        "Trending, Rose, Gold Tone, Party Wear, Gift Friendly", True, False, True,
        f"{_BASE}/d04adca3aaf741c8914edfea6b9266d29d641a9f2b041b340673eafb48847caa.png",
        "Rose quartz drop earrings by AAYNA",
    ),
    _product(
        "Minimal Silver Stud Earrings", "minimal-silver-stud-earrings", "EAR-SV-0003", "Earrings", "earrings",
        280, None, 95, 8, "Stainless steel-style alloy", "Silver", "Small",
        "Simple silver studs for clean everyday styling.",
        "Minimal silver-tone stud earrings for daily wear. Lightweight, easy to style, and suitable for office, university, or casual looks.",
        "Minimal, Silver Tone, Everyday Wear, Student Friendly, Under 300", False, True, True,
        f"{_BASE}/39080d5fde4f4cc63b9c8b450d560d368a08162caeae1ed075326af89193ecd3.png",
        "Minimal silver stud earrings by AAYNA",
    ),
    _product(
        "Layered Gold Chain Necklace", "layered-gold-chain-necklace", "NEC-GD-0001", "Necklaces", "necklaces",
        650, 599, 240, 4, "Alloy chain", "Gold", "Adjustable",
        "Layered gold necklace for a polished everyday look.",
        "A trendy layered gold-tone chain necklace that adds instant detail to simple outfits. Adjustable length for flexible styling.",
        "Best Seller, Gold Tone, Everyday Wear, Premium Look", True, True, True,
        f"{_BASE}/3f307bea99b2d4105f69754763cbc913835e2c5608a4da8cf7d73d49c0b8f2ad.png",
        "Layered gold chain necklace by AAYNA",
    ),
    _product(
        "Heart Pendant Necklace", "heart-pendant-necklace", "NEC-GD-0002", "Necklaces", "necklaces",
        480, 429, 170, 6, "Alloy pendant and chain", "Gold", "Adjustable",
        "A dainty heart pendant necklace for casual and gift styling.",
        "A simple gold-tone heart pendant necklace designed for everyday outfits and thoughtful gifting. Pairs well with earrings and rings.",
        "Gift Friendly, Gold Tone, Minimal, Everyday Wear", False, False, True,
        f"{_BASE}/ccb64ff518255ebb042108eb8875592025cc8959537a1474163010e614a32d31.png",
        "Gold heart pendant necklace by AAYNA",
    ),
    _product(
        "Adjustable Rose Stone Ring", "adjustable-rose-stone-ring", "RNG-RS-0001", "Rings", "rings",
        350, 319, 125, 7, "Alloy with rose stone", "Rose pink and gold", "Adjustable",
        "A soft rose stone ring with adjustable fit.",
        "A feminine adjustable ring featuring a rose-toned stone detail. Easy to wear and suitable for everyday or occasional styling.",
        "Rose, Adjustable, Gift Friendly, Gold Tone, Under 500", True, False, True,
        f"{_BASE}/4a56a96c4f3f9ab6219b5064cd3cae0f380e747ee09506291b67486ac21dba54.png",
        "Adjustable rose stone ring by AAYNA",
    ),
    _product(
        "Gold Stack Ring Set", "gold-stack-ring-set", "RNG-GD-0002", "Rings", "rings",
        420, 379, 150, 5, "Alloy ring set", "Gold", "Mixed adjustable sizes",
        "A set of gold-tone rings for layered styling.",
        "A trendy gold-tone stack ring set for mixing and matching. Designed for customers who like a styled, social-media-ready look.",
        "Trending, Gold Tone, Ring Set, Student Friendly, Under 500", False, True, True,
        f"{_BASE}/34e07594e45cb06c0d77a9bd60fa0ff2af2c2e463ea8d9c3e4b40c1ba12b2c1f.png",
        "Gold stack ring set by AAYNA",
    ),
    _product(
        "Pearl Charm Bracelet", "pearl-charm-bracelet", "BRC-PL-0001", "Bracelets", "bracelets",
        390, 349, 140, 6, "Alloy chain with artificial pearl charm", "Gold and pearl white", "Adjustable",
        "A delicate bracelet with a pearl charm detail.",
        "A soft and elegant gold-tone bracelet with a pearl charm. Works well for simple outfits, gifting, and matching with pearl earrings.",
        "Pearl, Gift Friendly, Gold Tone, Everyday Wear", True, False, True,
        f"{_BASE}/f062ca07a5ff90cb06ef76cd266915388471b6508b9fbc69f41de119b258b2ff.png",
        "Pearl charm bracelet by AAYNA",
    ),
    _product(
        "Blush Satin Scrunchie Set", "blush-satin-scrunchie-set", "HAR-PN-0001", "Hair Accessories", "hair-accessories",
        250, None, 85, 10, "Satin-style fabric", "Blush pink", "Set of 2",
        "Soft blush satin scrunchies for everyday hair styling.",
        "A set of soft blush satin-style scrunchies designed for daily hair styling. Gentle, feminine, and easy to pair with casual outfits.",
        "Student Friendly, Hair Accessory, Under 300, Everyday Wear", False, True, True,
        f"{_BASE}/839e86b70ec4ceb52481d4ba12ca61e2218d9472f5ae66764812fd59866572ae.png",
        "Blush satin scrunchie set by AAYNA",
    ),
    _product(
        "Gold Butterfly Hair Clip", "gold-butterfly-hair-clip", "HAR-GD-0002", "Hair Accessories", "hair-accessories",
        320, 299, 115, 8, "Metal alloy hair clip", "Gold", "One size",
        "A gold butterfly hair clip for soft feminine styling.",
        "A delicate gold-tone butterfly hair clip that adds a pretty accent to everyday and occasion hairstyles. Lightweight and easy to style.",
        "Trending, Gold Tone, Hair Accessory, Gift Friendly, Under 500", True, False, True,
        f"{_BASE}/4d93ac97dbfb2ec03559f773b0fb9db30336c9f193d3ea895a9f17cc23ec1632.png",
        "Gold butterfly hair clip by AAYNA",
    ),
]


# ---------------------------------------------------------------------------
# Website settings
# ---------------------------------------------------------------------------
SEED_SETTINGS = {
    "brand_name": "AAYNA",
    "tagline": "Reflect your everyday style.",
    "announcement_bar_text": "Free styling tips • Cash on Delivery across Bangladesh • Easy 3-day exchange",
    "hero_headline": "Everyday Accessories, Effortlessly Styled",
    "hero_subtitle": "Trendy, affordable, and feminine pieces selected for your everyday looks.",
    "hero_image_url": f"{_BASE}/2cbf31f9e9d3f71a5f10c8439ae11afade95867c1cab05d0ec37bb592c43c214.png",
    "delivery_charge_inside_dhaka": 80,
    "delivery_charge_outside_dhaka": 130,
    "free_delivery_threshold": 0,
    "cod_available": True,
    "whatsapp_number": "+8801XXXXXXXXX",
    "support_email": "hello@aayna.xyz",
    "bkash_number": "01XXXXXXXXX",
    "nagad_number": "01XXXXXXXXX",
    "instagram_handle": "@shopaayna.bd",
    "instagram_url": "https://instagram.com/shopaayna.bd",
    "facebook_url": "https://facebook.com/AAYNA-Bangladesh",
    "tiktok_url": "https://tiktok.com/@shopaayna.bd",
    "website_domain": "www.aayna.xyz",
    "currency": "BDT",
}


# ---------------------------------------------------------------------------
# Bangladesh districts (64)
# ---------------------------------------------------------------------------
BD_DISTRICTS = [
    "Bagerhat", "Bandarban", "Barguna", "Barishal", "Bhola", "Bogura", "Brahmanbaria",
    "Chandpur", "Chattogram", "Chuadanga", "Cox's Bazar", "Cumilla", "Dhaka", "Dinajpur",
    "Faridpur", "Feni", "Gaibandha", "Gazipur", "Gopalganj", "Habiganj", "Jamalpur",
    "Jashore", "Jhalokati", "Jhenaidah", "Joypurhat", "Khagrachhari", "Khulna",
    "Kishoreganj", "Kurigram", "Kushtia", "Lakshmipur", "Lalmonirhat", "Madaripur",
    "Magura", "Manikganj", "Meherpur", "Moulvibazar", "Munshiganj", "Mymensingh",
    "Naogaon", "Narail", "Narayanganj", "Narsingdi", "Natore", "Nawabganj", "Netrokona",
    "Nilphamari", "Noakhali", "Pabna", "Panchagarh", "Patuakhali", "Pirojpur", "Rajbari",
    "Rajshahi", "Rangamati", "Rangpur", "Satkhira", "Shariatpur", "Sherpur", "Sirajganj",
    "Sunamganj", "Sylhet", "Tangail", "Thakurgaon",
]

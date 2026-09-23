"""
AAYNA Backend API Launch Readiness Audit
NON-DESTRUCTIVE testing via direct HTTP API calls only.
DO NOT run pytest suite (it drops test databases).
"""
import requests
import json
import sys
from typing import Dict, List, Optional

# Base URL from frontend/.env
BASE_URL = "https://branch-status-4.preview.emergentagent.com/api"

# Admin credentials from backend/.env
ADMIN_EMAIL = "admin@aayna.xyz"
ADMIN_PASSWORD = "ChangeMe123!"

# Test customer data (fake Bangladesh data)
TEST_CUSTOMER = {
    "name": "Test Customer",
    "phone": "01712345678",
    "address": "House 12, Road 5, Dhanmondi, Dhaka",
    "district": "Dhaka"
}

# Fields that MUST NOT appear in public product endpoints (SECURITY)
FORBIDDEN_PRODUCT_FIELDS = [
    "cost_price", "supplier_price", "supplier_url", "landed_cost",
    "purchase_cost", "margin", "internal_notes", "sourcing_notes"
]

class TestResult:
    def __init__(self):
        self.passed = []
        self.failed = []
        self.p0_failures = []
        self.p1_failures = []
        self.p2_failures = []
    
    def add_pass(self, test_name: str, details: str = ""):
        self.passed.append({"test": test_name, "details": details})
        print(f"✅ PASS: {test_name}")
        if details:
            print(f"   {details}")
    
    def add_fail(self, test_name: str, severity: str, details: str, evidence: str = ""):
        failure = {
            "test": test_name,
            "severity": severity,
            "details": details,
            "evidence": evidence
        }
        self.failed.append(failure)
        if severity == "P0":
            self.p0_failures.append(failure)
        elif severity == "P1":
            self.p1_failures.append(failure)
        else:
            self.p2_failures.append(failure)
        print(f"❌ FAIL ({severity}): {test_name}")
        print(f"   {details}")
        if evidence:
            print(f"   Evidence: {evidence}")
    
    def summary(self):
        print("\n" + "="*80)
        print("AUDIT SUMMARY")
        print("="*80)
        print(f"Total Tests: {len(self.passed) + len(self.failed)}")
        print(f"Passed: {len(self.passed)}")
        print(f"Failed: {len(self.failed)}")
        print(f"  - P0 (Launch Blockers): {len(self.p0_failures)}")
        print(f"  - P1 (High Priority): {len(self.p1_failures)}")
        print(f"  - P2 (Medium Priority): {len(self.p2_failures)}")
        
        if self.p0_failures:
            print("\n🚨 P0 LAUNCH BLOCKERS:")
            for f in self.p0_failures:
                print(f"  - {f['test']}: {f['details']}")
        
        if self.p1_failures:
            print("\n⚠️  P1 HIGH PRIORITY:")
            for f in self.p1_failures:
                print(f"  - {f['test']}: {f['details']}")
        
        if self.p2_failures:
            print("\n⚡ P2 MEDIUM PRIORITY:")
            for f in self.p2_failures:
                print(f"  - {f['test']}: {f['details']}")
        
        return len(self.p0_failures) == 0

results = TestResult()

def check_forbidden_fields(data: dict, context: str) -> List[str]:
    """Check if any forbidden fields are present in the data."""
    found = []
    for field in FORBIDDEN_PRODUCT_FIELDS:
        if field in data:
            found.append(field)
    return found

def test_public_storefront_apis():
    """Test 1: PUBLIC STOREFRONT APIs"""
    print("\n" + "="*80)
    print("TEST 1: PUBLIC STOREFRONT APIs")
    print("="*80)
    
    # 1.1 Health check
    try:
        resp = requests.get(f"{BASE_URL}/health", timeout=10)
        if resp.status_code == 200 and resp.json().get("status") == "ok":
            results.add_pass("GET /api/health", f"Status: {resp.json()}")
        else:
            results.add_fail("GET /api/health", "P0", f"Expected 200 with status=ok, got {resp.status_code}", str(resp.text))
    except Exception as e:
        results.add_fail("GET /api/health", "P0", f"Request failed: {str(e)}")
    
    # 1.2 Health ready
    try:
        resp = requests.get(f"{BASE_URL}/health/ready", timeout=10)
        if resp.status_code == 200:
            results.add_pass("GET /api/health/ready", f"Status: {resp.json()}")
        else:
            results.add_fail("GET /api/health/ready", "P1", f"Expected 200, got {resp.status_code}", str(resp.text))
    except Exception as e:
        results.add_fail("GET /api/health/ready", "P1", f"Request failed: {str(e)}")
    
    # 1.3 Settings
    try:
        resp = requests.get(f"{BASE_URL}/settings", timeout=10)
        if resp.status_code == 200 and isinstance(resp.json(), dict):
            results.add_pass("GET /api/settings", f"Returned {len(resp.json())} settings")
        else:
            results.add_fail("GET /api/settings", "P0", f"Expected 200 with dict, got {resp.status_code}", str(resp.text))
    except Exception as e:
        results.add_fail("GET /api/settings", "P0", f"Request failed: {str(e)}")
    
    # 1.4 Districts
    try:
        resp = requests.get(f"{BASE_URL}/districts", timeout=10)
        if resp.status_code == 200 and isinstance(resp.json(), list):
            results.add_pass("GET /api/districts", f"Returned {len(resp.json())} districts")
        else:
            results.add_fail("GET /api/districts", "P0", f"Expected 200 with list, got {resp.status_code}", str(resp.text))
    except Exception as e:
        results.add_fail("GET /api/districts", "P0", f"Request failed: {str(e)}")
    
    # 1.5 Categories
    try:
        resp = requests.get(f"{BASE_URL}/categories", timeout=10)
        if resp.status_code == 200 and isinstance(resp.json(), list):
            results.add_pass("GET /api/categories", f"Returned {len(resp.json())} categories")
        else:
            results.add_fail("GET /api/categories", "P0", f"Expected 200 with list, got {resp.status_code}", str(resp.text))
    except Exception as e:
        results.add_fail("GET /api/categories", "P0", f"Request failed: {str(e)}")
    
    # 1.6 Products - CRITICAL SECURITY CHECK
    try:
        resp = requests.get(f"{BASE_URL}/products", timeout=10)
        if resp.status_code != 200:
            results.add_fail("GET /api/products", "P0", f"Expected 200, got {resp.status_code}", str(resp.text))
        else:
            products = resp.json()
            if not isinstance(products, list):
                results.add_fail("GET /api/products", "P0", "Expected list of products", str(resp.text))
            elif len(products) == 0:
                results.add_fail("GET /api/products", "P1", "No products returned (expected 10 seeded products)")
            else:
                # Check each product for forbidden fields
                security_violations = []
                status_violations = []
                for idx, product in enumerate(products):
                    forbidden = check_forbidden_fields(product, f"product {idx}")
                    if forbidden:
                        security_violations.append(f"Product {product.get('slug', idx)}: {', '.join(forbidden)}")
                    # Check status filter
                    status = product.get("status")
                    if status not in ["active", "out_of_stock"]:
                        status_violations.append(f"Product {product.get('slug', idx)}: status={status}")
                
                if security_violations:
                    results.add_fail(
                        "GET /api/products - SECURITY VIOLATION",
                        "P0",
                        "FORBIDDEN FIELDS EXPOSED: " + "; ".join(security_violations),
                        f"Products contain private fields: {security_violations}"
                    )
                elif status_violations:
                    results.add_fail(
                        "GET /api/products - Status Filter",
                        "P0",
                        "Inactive/draft products exposed: " + "; ".join(status_violations)
                    )
                else:
                    # List all fields returned for verification
                    sample_fields = list(products[0].keys()) if products else []
                    results.add_pass(
                        "GET /api/products - Security Check",
                        f"Returned {len(products)} products. Fields: {', '.join(sample_fields)}. No forbidden fields found."
                    )
    except Exception as e:
        results.add_fail("GET /api/products", "P0", f"Request failed: {str(e)}")
    
    # 1.7 Product Detail - CRITICAL SECURITY CHECK
    # First get a product slug
    try:
        resp = requests.get(f"{BASE_URL}/products", timeout=10)
        if resp.status_code == 200 and len(resp.json()) > 0:
            product_slug = resp.json()[0].get("slug")
            if product_slug:
                resp = requests.get(f"{BASE_URL}/products/{product_slug}", timeout=10)
                if resp.status_code != 200:
                    results.add_fail(f"GET /api/products/{product_slug}", "P0", f"Expected 200, got {resp.status_code}", str(resp.text))
                else:
                    data = resp.json()
                    product = data.get("product", {})
                    related = data.get("related", [])
                    
                    # Check main product for forbidden fields
                    forbidden_main = check_forbidden_fields(product, "main product")
                    forbidden_related = []
                    for idx, rel in enumerate(related):
                        forbidden = check_forbidden_fields(rel, f"related product {idx}")
                        if forbidden:
                            forbidden_related.extend(forbidden)
                    
                    if forbidden_main or forbidden_related:
                        all_forbidden = forbidden_main + forbidden_related
                        results.add_fail(
                            f"GET /api/products/{product_slug} - SECURITY VIOLATION",
                            "P0",
                            f"FORBIDDEN FIELDS EXPOSED: {', '.join(set(all_forbidden))}",
                            f"Main: {forbidden_main}, Related: {forbidden_related}"
                        )
                    else:
                        sample_fields = list(product.keys()) if product else []
                        results.add_pass(
                            f"GET /api/products/{product_slug} - Security Check",
                            f"Fields: {', '.join(sample_fields)}. No forbidden fields found. Related products: {len(related)}"
                        )
    except Exception as e:
        results.add_fail("GET /api/products/{slug}", "P0", f"Request failed: {str(e)}")

def test_cart_validation():
    """Test 2: CART VALIDATION"""
    print("\n" + "="*80)
    print("TEST 2: CART VALIDATION")
    print("="*80)
    
    # Get a valid product first
    try:
        resp = requests.get(f"{BASE_URL}/products", timeout=10)
        if resp.status_code == 200 and len(resp.json()) > 0:
            valid_product_id = resp.json()[0].get("id")
            
            # 2.1 Valid cart validation (Dhaka)
            payload = {
                "items": [{"product_id": valid_product_id, "quantity": 1}],
                "district": "Dhaka"
            }
            resp = requests.post(f"{BASE_URL}/cart/validate", json=payload, timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                delivery_dhaka = data.get("delivery_charge")
                results.add_pass(
                    "POST /api/cart/validate (Dhaka)",
                    f"Subtotal: {data.get('subtotal')}, Delivery: {delivery_dhaka}, Total: {data.get('total')}"
                )
            else:
                results.add_fail("POST /api/cart/validate (Dhaka)", "P0", f"Expected 200, got {resp.status_code}", str(resp.text))
            
            # 2.2 Valid cart validation (non-Dhaka)
            payload["district"] = "Chittagong"
            resp = requests.post(f"{BASE_URL}/cart/validate", json=payload, timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                delivery_non_dhaka = data.get("delivery_charge")
                results.add_pass(
                    "POST /api/cart/validate (Chittagong)",
                    f"Subtotal: {data.get('subtotal')}, Delivery: {delivery_non_dhaka}, Total: {data.get('total')}"
                )
                # Verify delivery charge difference
                if delivery_dhaka and delivery_non_dhaka and delivery_non_dhaka > delivery_dhaka:
                    results.add_pass("Delivery charge logic", f"Dhaka: {delivery_dhaka}, Non-Dhaka: {delivery_non_dhaka}")
                elif delivery_dhaka and delivery_non_dhaka:
                    results.add_fail("Delivery charge logic", "P2", f"Expected non-Dhaka ({delivery_non_dhaka}) > Dhaka ({delivery_dhaka})")
            else:
                results.add_fail("POST /api/cart/validate (Chittagong)", "P0", f"Expected 200, got {resp.status_code}", str(resp.text))
            
            # 2.3 Invalid product ID
            payload = {
                "items": [{"product_id": "invalid-product-id-12345", "quantity": 1}],
                "district": "Dhaka"
            }
            resp = requests.post(f"{BASE_URL}/cart/validate", json=payload, timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                if data.get("has_issue") and not data.get("items", [{}])[0].get("available"):
                    results.add_pass("POST /api/cart/validate (invalid product)", "Correctly marked as unavailable")
                else:
                    results.add_fail("POST /api/cart/validate (invalid product)", "P1", "Should mark invalid product as unavailable", str(data))
            else:
                results.add_fail("POST /api/cart/validate (invalid product)", "P1", f"Expected 200, got {resp.status_code}", str(resp.text))
    except Exception as e:
        results.add_fail("POST /api/cart/validate", "P0", f"Request failed: {str(e)}")

def test_checkout_order_creation():
    """Test 3: CHECKOUT / ORDER CREATION (P0)"""
    print("\n" + "="*80)
    print("TEST 3: CHECKOUT / ORDER CREATION")
    print("="*80)
    
    global test_order_number, test_order_token, test_order_phone
    test_order_number = None
    test_order_token = None
    test_order_phone = TEST_CUSTOMER["phone"]
    
    # Get a valid product and payment method
    try:
        resp = requests.get(f"{BASE_URL}/products", timeout=10)
        products = resp.json()
        if not products:
            results.add_fail("Checkout setup", "P0", "No products available for checkout test")
            return
        
        valid_product = products[0]
        product_id = valid_product.get("id")
        
        # Get valid payment method
        resp = requests.get(f"{BASE_URL}/settings", timeout=10)
        settings = resp.json()
        # Use COD as it's always available
        payment_method = "cod"
        
        # 3.1 Create order
        import uuid
        client_request_id = str(uuid.uuid4())
        
        payload = {
            "customer_name": TEST_CUSTOMER["name"],
            "customer_phone": TEST_CUSTOMER["phone"],
            "district": TEST_CUSTOMER["district"],
            "delivery_address": TEST_CUSTOMER["address"],
            "delivery_note": "Test order - please ignore",
            "customer_email": "",
            "payment_method": payment_method,
            "transaction_id": "",
            "sender_number": "",
            "items": [{"product_id": product_id, "quantity": 1}],
            "client_request_id": client_request_id
        }
        
        resp = requests.post(f"{BASE_URL}/checkout", json=payload, timeout=10)
        if resp.status_code != 200:
            results.add_fail("POST /api/checkout", "P0", f"Expected 200, got {resp.status_code}", str(resp.text))
            return
        
        data = resp.json()
        test_order_number = data.get("order_number")
        test_order_token = data.get("order_confirmation_token")
        
        if not test_order_number or not test_order_token:
            results.add_fail("POST /api/checkout", "P0", "Missing order_number or order_confirmation_token", str(data))
            return
        
        if data.get("duplicate"):
            results.add_fail("POST /api/checkout", "P0", "First checkout marked as duplicate", str(data))
            return
        
        results.add_pass(
            "POST /api/checkout - Order Creation",
            f"Order: {test_order_number}, Token received: {test_order_token[:10]}..."
        )
        
        # 3.2 Test idempotency - duplicate submission
        resp = requests.post(f"{BASE_URL}/checkout", json=payload, timeout=10)
        if resp.status_code != 200:
            results.add_fail("POST /api/checkout (duplicate)", "P0", f"Expected 200, got {resp.status_code}", str(resp.text))
        else:
            data = resp.json()
            if data.get("duplicate") and data.get("order_number") == test_order_number:
                results.add_pass(
                    "POST /api/checkout - Idempotency",
                    f"Duplicate detected, same order returned: {test_order_number}"
                )
            else:
                results.add_fail(
                    "POST /api/checkout - Idempotency",
                    "P0",
                    "Duplicate submission created new order or didn't return duplicate flag",
                    str(data)
                )
        
        # 3.3 Test over-quantity (try to order more than stock)
        # Get stock quantity
        stock = valid_product.get("stock_quantity", 0)
        if stock > 0:
            payload_overstock = payload.copy()
            payload_overstock["client_request_id"] = str(uuid.uuid4())
            payload_overstock["items"] = [{"product_id": product_id, "quantity": stock + 100}]
            
            resp = requests.post(f"{BASE_URL}/checkout", json=payload_overstock, timeout=10)
            if resp.status_code == 400:
                results.add_pass(
                    "POST /api/checkout - Over-quantity",
                    f"Correctly rejected order exceeding stock (requested {stock + 100}, available {stock})"
                )
            else:
                results.add_fail(
                    "POST /api/checkout - Over-quantity",
                    "P0",
                    f"Should reject over-quantity order with 400, got {resp.status_code}",
                    str(resp.text)
                )
    except Exception as e:
        results.add_fail("POST /api/checkout", "P0", f"Request failed: {str(e)}")

def test_order_confirmation_tracking():
    """Test 4: ORDER CONFIRMATION + TRACKING PRIVACY"""
    print("\n" + "="*80)
    print("TEST 4: ORDER CONFIRMATION + TRACKING PRIVACY")
    print("="*80)
    
    if not test_order_number or not test_order_token:
        results.add_fail("Order confirmation/tracking", "P0", "No test order available (checkout failed)")
        return
    
    # 4.1 Order confirmation with valid token
    try:
        resp = requests.get(f"{BASE_URL}/orders/{test_order_number}?token={test_order_token}", timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            if data.get("order_number") == test_order_number:
                results.add_pass(
                    "GET /api/orders/{order_number} with token",
                    f"Order confirmed: {test_order_number}, Total: {data.get('total_amount')}"
                )
            else:
                results.add_fail(
                    "GET /api/orders/{order_number} with token",
                    "P0",
                    "Order number mismatch",
                    str(data)
                )
        else:
            results.add_fail(
                "GET /api/orders/{order_number} with token",
                "P0",
                f"Expected 200, got {resp.status_code}",
                str(resp.text)
            )
    except Exception as e:
        results.add_fail("GET /api/orders/{order_number} with token", "P0", f"Request failed: {str(e)}")
    
    # 4.2 Order confirmation without token (SECURITY)
    try:
        resp = requests.get(f"{BASE_URL}/orders/{test_order_number}", timeout=10)
        if resp.status_code == 404:
            results.add_pass(
                "GET /api/orders/{order_number} without token - SECURITY",
                "Correctly returns 404 (privacy protected)"
            )
        else:
            results.add_fail(
                "GET /api/orders/{order_number} without token - SECURITY",
                "P0",
                f"SECURITY VIOLATION: Should return 404 without token, got {resp.status_code}",
                str(resp.text)
            )
    except Exception as e:
        results.add_fail("GET /api/orders/{order_number} without token", "P0", f"Request failed: {str(e)}")
    
    # 4.3 Order confirmation with wrong token (SECURITY)
    try:
        resp = requests.get(f"{BASE_URL}/orders/{test_order_number}?token=wrong-token-12345", timeout=10)
        if resp.status_code == 404:
            results.add_pass(
                "GET /api/orders/{order_number} with wrong token - SECURITY",
                "Correctly returns 404 (privacy protected)"
            )
        else:
            results.add_fail(
                "GET /api/orders/{order_number} with wrong token - SECURITY",
                "P0",
                f"SECURITY VIOLATION: Should return 404 with wrong token, got {resp.status_code}",
                str(resp.text)
            )
    except Exception as e:
        results.add_fail("GET /api/orders/{order_number} with wrong token", "P0", f"Request failed: {str(e)}")
    
    # 4.4 Track order with correct phone
    try:
        payload = {
            "order_number": test_order_number,
            "phone": test_order_phone
        }
        resp = requests.post(f"{BASE_URL}/track", json=payload, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            if isinstance(data, list) and len(data) > 0 and data[0].get("order_number") == test_order_number:
                results.add_pass(
                    "POST /api/track with correct phone",
                    f"Order tracked: {test_order_number}, Status: {data[0].get('order_status')}"
                )
            else:
                results.add_fail(
                    "POST /api/track with correct phone",
                    "P0",
                    "Unexpected response format",
                    str(data)
                )
        else:
            results.add_fail(
                "POST /api/track with correct phone",
                "P0",
                f"Expected 200, got {resp.status_code}",
                str(resp.text)
            )
    except Exception as e:
        results.add_fail("POST /api/track with correct phone", "P0", f"Request failed: {str(e)}")
    
    # 4.5 Track order with wrong phone (SECURITY)
    try:
        payload = {
            "order_number": test_order_number,
            "phone": "01798765432"  # Different phone
        }
        resp = requests.post(f"{BASE_URL}/track", json=payload, timeout=10)
        if resp.status_code == 404:
            results.add_pass(
                "POST /api/track with wrong phone - SECURITY",
                "Correctly returns 404 (privacy protected)"
            )
        else:
            results.add_fail(
                "POST /api/track with wrong phone - SECURITY",
                "P0",
                f"SECURITY VIOLATION: Should return 404 with wrong phone, got {resp.status_code}",
                str(resp.text)
            )
    except Exception as e:
        results.add_fail("POST /api/track with wrong phone", "P0", f"Request failed: {str(e)}")
    
    # 4.6 Track order with only order number (SECURITY)
    try:
        payload = {
            "order_number": test_order_number,
            "phone": ""
        }
        resp = requests.post(f"{BASE_URL}/track", json=payload, timeout=10)
        if resp.status_code in [400, 404]:
            results.add_pass(
                "POST /api/track without phone - SECURITY",
                f"Correctly rejects (status {resp.status_code})"
            )
        else:
            results.add_fail(
                "POST /api/track without phone - SECURITY",
                "P0",
                f"SECURITY VIOLATION: Should reject without phone, got {resp.status_code}",
                str(resp.text)
            )
    except Exception as e:
        results.add_fail("POST /api/track without phone", "P0", f"Request failed: {str(e)}")

def test_admin_auth_operations():
    """Test 5: ADMIN AUTH + OPERATIONS"""
    print("\n" + "="*80)
    print("TEST 5: ADMIN AUTH + OPERATIONS")
    print("="*80)
    
    global admin_token
    admin_token = None
    
    # 5.1 Admin login
    try:
        payload = {
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        }
        resp = requests.post(f"{BASE_URL}/admin/login", json=payload, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            admin_token = data.get("token")
            if admin_token:
                results.add_pass(
                    "POST /api/admin/login",
                    f"Admin logged in: {data.get('user', {}).get('email')}"
                )
            else:
                results.add_fail("POST /api/admin/login", "P0", "No token returned", str(data))
                return
        else:
            results.add_fail("POST /api/admin/login", "P0", f"Expected 200, got {resp.status_code}", str(resp.text))
            return
    except Exception as e:
        results.add_fail("POST /api/admin/login", "P0", f"Request failed: {str(e)}")
        return
    
    # 5.2 Unauthenticated request to admin route (SECURITY)
    try:
        resp = requests.get(f"{BASE_URL}/admin/orders", timeout=10)
        if resp.status_code in [401, 403]:
            results.add_pass(
                "GET /api/admin/orders without auth - SECURITY",
                f"Correctly rejected with {resp.status_code}"
            )
        else:
            results.add_fail(
                "GET /api/admin/orders without auth - SECURITY",
                "P0",
                f"SECURITY VIOLATION: Should reject unauthenticated request, got {resp.status_code}",
                str(resp.text)
            )
    except Exception as e:
        results.add_fail("GET /api/admin/orders without auth", "P0", f"Request failed: {str(e)}")
    
    # Headers for authenticated requests
    headers = {"Authorization": f"Bearer {admin_token}"}
    
    # 5.3 Admin dashboard
    try:
        resp = requests.get(f"{BASE_URL}/admin/dashboard", headers=headers, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            results.add_pass(
                "GET /api/admin/dashboard",
                f"Total orders: {data.get('total_orders')}, New orders: {data.get('new_orders')}"
            )
        else:
            results.add_fail("GET /api/admin/dashboard", "P1", f"Expected 200, got {resp.status_code}", str(resp.text))
    except Exception as e:
        results.add_fail("GET /api/admin/dashboard", "P1", f"Request failed: {str(e)}")
    
    # 5.4 Admin orders list
    try:
        resp = requests.get(f"{BASE_URL}/admin/orders", headers=headers, timeout=10)
        if resp.status_code == 200:
            orders = resp.json()
            # Check if our test order is in the list
            test_order_found = any(o.get("order_number") == test_order_number for o in orders)
            if test_order_found:
                results.add_pass(
                    "GET /api/admin/orders",
                    f"Returned {len(orders)} orders, including test order {test_order_number}"
                )
            else:
                results.add_fail(
                    "GET /api/admin/orders",
                    "P0",
                    f"Test order {test_order_number} not found in admin orders list",
                    f"Total orders: {len(orders)}"
                )
        else:
            results.add_fail("GET /api/admin/orders", "P0", f"Expected 200, got {resp.status_code}", str(resp.text))
    except Exception as e:
        results.add_fail("GET /api/admin/orders", "P0", f"Request failed: {str(e)}")
    
    # 5.5 Admin order detail
    if test_order_number:
        try:
            resp = requests.get(f"{BASE_URL}/admin/orders/{test_order_number}", headers=headers, timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                results.add_pass(
                    f"GET /api/admin/orders/{test_order_number}",
                    f"Order details: Status={data.get('order_status')}, Total={data.get('total_amount')}, Items={len(data.get('items', []))}"
                )
            else:
                results.add_fail(
                    f"GET /api/admin/orders/{test_order_number}",
                    "P0",
                    f"Expected 200, got {resp.status_code}",
                    str(resp.text)
                )
        except Exception as e:
            results.add_fail(f"GET /api/admin/orders/{test_order_number}", "P0", f"Request failed: {str(e)}")
    
    # 5.6 Update order status
    if test_order_number:
        try:
            payload = {"order_status": "Confirmed"}
            resp = requests.put(f"{BASE_URL}/admin/orders/{test_order_number}", json=payload, headers=headers, timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                if data.get("order_status") == "Confirmed":
                    results.add_pass(
                        f"PUT /api/admin/orders/{test_order_number}",
                        "Order status updated to Confirmed"
                    )
                    
                    # 5.7 Verify customer tracking reflects new status
                    track_payload = {
                        "order_number": test_order_number,
                        "phone": test_order_phone
                    }
                    resp = requests.post(f"{BASE_URL}/track", json=track_payload, timeout=10)
                    if resp.status_code == 200:
                        track_data = resp.json()
                        if track_data and track_data[0].get("order_status") == "Confirmed":
                            results.add_pass(
                                "Order status sync to customer tracking",
                                "Customer tracking reflects updated status: Confirmed"
                            )
                        else:
                            results.add_fail(
                                "Order status sync to customer tracking",
                                "P1",
                                f"Customer tracking shows {track_data[0].get('order_status')}, expected Confirmed"
                            )
                else:
                    results.add_fail(
                        f"PUT /api/admin/orders/{test_order_number}",
                        "P0",
                        "Order status not updated",
                        str(data)
                    )
            else:
                results.add_fail(
                    f"PUT /api/admin/orders/{test_order_number}",
                    "P0",
                    f"Expected 200, got {resp.status_code}",
                    str(resp.text)
                )
        except Exception as e:
            results.add_fail(f"PUT /api/admin/orders/{test_order_number}", "P0", f"Request failed: {str(e)}")
    
    # 5.8 Admin products
    try:
        resp = requests.get(f"{BASE_URL}/admin/products", headers=headers, timeout=10)
        if resp.status_code == 200:
            products = resp.json()
            # Admin view MAY include internal fields
            sample_fields = list(products[0].keys()) if products else []
            results.add_pass(
                "GET /api/admin/products",
                f"Returned {len(products)} products. Admin fields: {', '.join(sample_fields)}"
            )
        else:
            results.add_fail("GET /api/admin/products", "P1", f"Expected 200, got {resp.status_code}", str(resp.text))
    except Exception as e:
        results.add_fail("GET /api/admin/products", "P1", f"Request failed: {str(e)}")
    
    # 5.9 Admin categories
    try:
        resp = requests.get(f"{BASE_URL}/admin/categories", headers=headers, timeout=10)
        if resp.status_code == 200:
            categories = resp.json()
            results.add_pass("GET /api/admin/categories", f"Returned {len(categories)} categories")
        else:
            results.add_fail("GET /api/admin/categories", "P1", f"Expected 200, got {resp.status_code}", str(resp.text))
    except Exception as e:
        results.add_fail("GET /api/admin/categories", "P1", f"Request failed: {str(e)}")
    
    # 5.10 Admin customers
    try:
        resp = requests.get(f"{BASE_URL}/admin/customers", headers=headers, timeout=10)
        if resp.status_code == 200:
            customers = resp.json()
            results.add_pass("GET /api/admin/customers", f"Returned {len(customers)} customers")
        else:
            results.add_fail("GET /api/admin/customers", "P1", f"Expected 200, got {resp.status_code}", str(resp.text))
    except Exception as e:
        results.add_fail("GET /api/admin/customers", "P1", f"Request failed: {str(e)}")
    
    # 5.11 Admin settings
    try:
        resp = requests.get(f"{BASE_URL}/admin/settings", headers=headers, timeout=10)
        if resp.status_code == 200:
            settings = resp.json()
            results.add_pass("GET /api/admin/settings", f"Returned {len(settings)} settings")
        else:
            results.add_fail("GET /api/admin/settings", "P1", f"Expected 200, got {resp.status_code}", str(resp.text))
    except Exception as e:
        results.add_fail("GET /api/admin/settings", "P1", f"Request failed: {str(e)}")

def main():
    print("="*80)
    print("AAYNA BACKEND API LAUNCH READINESS AUDIT")
    print("NON-DESTRUCTIVE TESTING")
    print("="*80)
    print(f"Base URL: {BASE_URL}")
    print(f"Admin: {ADMIN_EMAIL}")
    print(f"Test Customer: {TEST_CUSTOMER['name']} ({TEST_CUSTOMER['phone']})")
    print("="*80)
    
    # Run all tests
    test_public_storefront_apis()
    test_cart_validation()
    test_checkout_order_creation()
    test_order_confirmation_tracking()
    test_admin_auth_operations()
    
    # Print summary
    success = results.summary()
    
    # Exit with appropriate code
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()

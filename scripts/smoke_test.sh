#!/usr/bin/env bash
# AAYNA — non-destructive production smoke test.
# Checks public read-only endpoints only. Does NOT place orders or mutate data.
#
# Usage:
#   BASE_URL=https://www.aayna.com.bd ./scripts/smoke_test.sh
#   (defaults to REACT_APP_BACKEND_URL from frontend/.env)

set -euo pipefail

BASE_URL="${BASE_URL:-}"
if [ -z "$BASE_URL" ] && [ -f "$(dirname "$0")/../frontend/.env" ]; then
  BASE_URL=$(grep '^REACT_APP_BACKEND_URL=' "$(dirname "$0")/../frontend/.env" | cut -d= -f2-)
fi
BASE_URL="${BASE_URL%/}"
API="$BASE_URL/api"

echo "Smoke testing: $BASE_URL"
fail=0

check() {
  local name="$1" url="$2" expect="$3"
  code=$(curl -s -o /tmp/smoke_body -w "%{http_code}" "$url" || echo "000")
  if [ "$code" = "$expect" ]; then
    echo "  ✓ $name ($code)"
  else
    echo "  ✗ $name — expected $expect, got $code"
    fail=1
  fi
}

check "health"        "$API/health"        200
check "ready"         "$API/health/ready"  200
check "products"      "$API/products"      200
check "categories"    "$API/categories"    200
check "settings"      "$API/settings"      200
check "sitemap.xml"   "$API/sitemap.xml"   200
check "robots.txt"    "$API/robots.txt"    200

if [ "$fail" = "0" ]; then
  echo "All smoke checks passed."
else
  echo "Some smoke checks FAILED."
  exit 1
fi

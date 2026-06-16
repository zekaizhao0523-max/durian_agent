from __future__ import annotations

from src.storage.db import get_order, get_product, get_trace_batch, init_db, list_products, seed_demo_catalog


init_db()

products = list_products()
assert len(products) >= 4
print("OK products from pgsql:", len(products))

batch = get_trace_batch("TR20260609002")
assert batch and batch.get("valid")
print("OK trace batch:", batch["variety"])

product = get_product("sku_101")
assert product and product["price"] == 268
print("OK product:", product["name"])

order = get_order("ORD_10001")
assert order and order["user_id"] == "demo_user"
print("OK order:", order["order_id"])

reseed = seed_demo_catalog()
assert reseed.get("skipped") is True
print("OK seed idempotent")

print("ALL CATALOG TESTS PASSED")

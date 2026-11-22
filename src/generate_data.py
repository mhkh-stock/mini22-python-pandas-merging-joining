"""Regenerate data/raw/*_SAMPLE.csv — Mini #22 sample data.

Fictional shop "Noor Electronics" — the same made-up Pakistani
electronics store as Mini #1 / #3 / #10 / #15 / #16, so the clean
orders reconcile to the same total: 32 orders, 52 order lines,
PKR 346,800 revenue, Jan–Jun 2026. SAMPLE / DEMO data only — never
real client or real business data.

On top of the clean Mini #1 data this pack plants the exact mess a
merging/joining pack needs to teach on — every planted row is
deliberate and documented in data/README.md:

  * products: product_id 2 listed TWICE (duplicate key, two prices).
  * customers: customer_id 7 listed TWICE (duplicate key, two cities).
  * orders: order 33 has customer_id "CUST-05" (string key that
    does not match customer 5 — mismatched key format/casing).
  * order_items: 3 extra lines — line 53 (order 33, good product,
    bad customer), line 54 (product 99, which does not exist),
    line 55 (product "P-03", a string key that does not match
    product 3). The 52 clean lines still total PKR 346,800.
  * monthly extracts: line 22 is sent twice (March file and April
    file) — the duplicate a concat has to catch.
  * returns: 1 return for order 99, which does not exist.
  * employees: E06 reports to manager E99, who does not exist.

Fully deterministic (no randomness): re-running this script
reproduces every file byte-for-byte (src/checks.py verifies that).

Usage: python3 src/generate_data.py [--out-dir DIR]
"""

import argparse
import csv
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUT = ROOT / "data" / "raw"

# --- Canonical Mini #1 / #3 data (clean) -------------------------------
# customers: customer_id, name, city, signup_date
CUSTOMERS = [
    (1, "Ayesha Khan", "Lahore", "2025-11-02"),
    (2, "Bilal Ahmed", "Karachi", "2025-12-10"),
    (3, "Fatima Noor", "Islamabad", "2026-01-05"),
    (4, "Usman Tariq", "Lahore", "2026-01-20"),
    (5, "Zainab Ali", "Karachi", "2026-02-03"),
    (6, "Hassan Raza", "Faisalabad", "2026-02-15"),
    (7, "Maryam Iqbal", "Islamabad", "2026-03-01"),
    (8, "Omar Sheikh", "Lahore", "2026-03-10"),
    (9, "Sana Malik", "Karachi", "2026-03-22"),
    (10, "Ali Nawaz", "Multan", "2026-04-05"),
    (11, "Hira Shah", "Peshawar", "2026-05-02"),
    (12, "Danish Iqbal", "Quetta", "2026-05-19"),
]
# Planted duplicate key: customer 7 twice (second row, another city).
CUSTOMERS_EXTRA = [
    (7, "Maryam Iqbal", "Rawalpindi", "2026-03-01"),
]

# products: product_id, product_name, category, price_pkr
PRODUCTS = [
    (1, "Wireless Mouse", "Electronics", 2500),
    (2, "Mechanical Keyboard", "Electronics", 8500),
    (3, "Laptop Stand", "Electronics", 4500),
    (4, "Office Chair", "Furniture", 18000),
    (5, "Desk Lamp", "Furniture", 4200),
    (6, "Notebook Set", "Stationery", 1200),
    (7, "Ceramic Mug Set", "Kitchen", 3200),
    (8, "Dinner Set 24pc", "Kitchen", 14500),
    (9, "Bluetooth Speaker", "Electronics", 6500),
]
# Planted duplicate key: product 2 twice (old listing, old price).
PRODUCTS_EXTRA = [
    (2, "Mechanical Keyboard - old listing", "Electronics", 8000),
]

# orders: order_id, customer_id, order_date
ORDERS = [
    (1, 1, "2026-01-08"), (2, 1, "2026-02-14"), (3, 1, "2026-04-02"),
    (4, 2, "2026-01-15"), (5, 2, "2026-03-20"), (6, 2, "2026-05-11"),
    (7, 3, "2026-01-22"), (8, 3, "2026-02-28"), (9, 3, "2026-06-05"),
    (10, 4, "2026-02-05"), (11, 4, "2026-04-18"),
    (12, 5, "2026-02-12"), (13, 5, "2026-05-25"),
    (14, 6, "2026-03-03"), (15, 6, "2026-03-29"), (16, 6, "2026-06-12"),
    (17, 7, "2026-03-15"), (18, 7, "2026-04-22"),
    (19, 8, "2026-01-30"), (20, 8, "2026-05-08"),
    (21, 9, "2026-04-10"), (22, 9, "2026-06-20"),
    (23, 10, "2026-04-15"), (24, 10, "2026-05-30"),
    (25, 1, "2026-06-18"), (26, 2, "2026-06-25"),
    (27, 4, "2026-06-02"), (28, 5, "2026-01-19"),
    (29, 7, "2026-06-28"), (30, 8, "2026-02-21"),
    (31, 9, "2026-02-08"), (32, 3, "2026-05-14"),
]
# Planted mismatched key: customer_id as a string that will not join.
ORDERS_EXTRA = [
    (33, "CUST-05", "2026-06-30"),
]

# order_items: line_id, order_id, product_id, quantity, unit_price_pkr
ORDER_ITEMS = [
    (1, 1, 1, 2, 2500), (2, 1, 6, 3, 1200),
    (3, 2, 2, 1, 8500), (4, 2, 7, 2, 3200),
    (5, 3, 4, 1, 18000),
    (6, 4, 1, 1, 2500), (7, 4, 3, 1, 4500),
    (8, 5, 8, 1, 14500),
    (9, 6, 2, 1, 8500), (10, 6, 5, 2, 4200),
    (11, 7, 6, 5, 1200),
    (12, 8, 1, 2, 2500), (13, 8, 7, 1, 3200),
    (14, 9, 3, 1, 4500), (15, 9, 8, 1, 14500),
    (16, 10, 5, 1, 4200),
    (17, 11, 4, 1, 18000), (18, 11, 6, 2, 1200),
    (19, 12, 7, 3, 3200),
    (20, 13, 2, 1, 8500), (21, 13, 1, 1, 2500),
    (22, 14, 6, 4, 1200),
    (23, 15, 1, 1, 2500), (24, 15, 5, 1, 4200),
    (25, 16, 8, 1, 14500),
    (26, 17, 3, 1, 4500),
    (27, 18, 2, 1, 8500), (28, 18, 7, 2, 3200),
    (29, 19, 1, 3, 2500),
    (30, 20, 4, 1, 18000),
    (31, 21, 6, 2, 1200),
    (32, 22, 8, 1, 14500), (33, 22, 5, 1, 4200),
    (34, 23, 7, 2, 3200),
    (35, 24, 2, 1, 8500),
    (36, 25, 5, 2, 4200), (37, 25, 6, 3, 1200),
    (38, 26, 1, 2, 2500),
    (39, 27, 3, 1, 4500), (40, 27, 1, 1, 2500),
    (41, 28, 6, 4, 1200),
    (42, 29, 4, 1, 18000),
    (43, 30, 5, 1, 4200), (44, 30, 7, 1, 3200),
    (45, 31, 1, 1, 2500),
    (46, 32, 2, 1, 8500), (47, 32, 6, 2, 1200),
    (48, 1, 7, 1, 3200),
    (49, 6, 7, 1, 3200),
    (50, 10, 7, 1, 3200),
    (51, 20, 6, 1, 1200),
    (52, 24, 7, 1, 3200),
]
# Planted bad-key lines (line_id 53-55). They are NOT part of the
# PKR 346,800 clean total.
ORDER_ITEMS_EXTRA = [
    # order 33 exists but its customer key is bad; the product is fine.
    (53, 33, 1, 1, 2500),
    # product 99 does not exist in the catalogue.
    (54, 5, 99, 2, 6500),
    # product key in the wrong format ("P-03" instead of 3).
    (55, 12, "P-03", 1, 4500),
]

# employees: employee_id, name, role, manager_id ("" = no manager)
EMPLOYEES = [
    ("E01", "Ayesha Khan", "Owner", ""),
    ("E02", "Bilal Ahmed", "Sales Lead", "E01"),
    ("E03", "Fatima Noor", "Sales Assistant", "E01"),
    ("E04", "Usman Tariq", "Warehouse Lead", "E02"),
    ("E05", "Zainab Ali", "Support Agent", "E02"),
    # Planted orphan: manager E99 does not exist (left the shop).
    ("E06", "Hassan Raza", "Delivery Rider", "E99"),
]

# returns: return_id, order_id, product_id, qty_returned, reason
RETURNS = [
    (1, 6, 2, 1, "faulty keys"),
    (2, 15, 1, 1, "changed mind"),
    (3, 22, 8, 1, "damaged in transit"),
    (4, 3, 4, 1, "too big"),
    # Planted orphan: order 99 does not exist.
    (5, 99, 1, 1, "no such order"),
]

# price_history: product_id, effective_from, price_pkr
# Three products changed price mid-year; the rest held flat.
PRICE_HISTORY = [
    (1, "2026-01-01", 2500), (1, "2026-04-01", 2300),
    (2, "2026-01-01", 8500), (2, "2026-03-01", 9000),
    (3, "2026-01-01", 4500),
    (4, "2026-01-01", 18000),
    (5, "2026-01-01", 4200),
    (6, "2026-01-01", 1200),
    (7, "2026-01-01", 3200),
    (8, "2026-01-01", 14500), (8, "2026-05-01", 13900),
    (9, "2026-01-01", 6500),
]

# The monthly extracts re-send one line: line 22 (March) also appears
# in the April file. The concat technique has to catch it.
DUPLICATE_LINE_IN_APRIL = 22


def _write(path, header, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(rows)
    print(f"Wrote {path} ({len(rows)} rows)")


def main(out_dir=DEFAULT_OUT):
    out_dir = Path(out_dir)
    _write(out_dir / "orders_SAMPLE.csv",
           ["order_id", "customer_id", "order_date"],
           list(ORDERS) + list(ORDERS_EXTRA))
    _write(out_dir / "order_items_SAMPLE.csv",
           ["line_id", "order_id", "product_id", "quantity",
            "unit_price_pkr"],
           list(ORDER_ITEMS) + list(ORDER_ITEMS_EXTRA))
    _write(out_dir / "products_SAMPLE.csv",
           ["product_id", "product_name", "category", "price_pkr"],
           list(PRODUCTS) + list(PRODUCTS_EXTRA))
    _write(out_dir / "customers_SAMPLE.csv",
           ["customer_id", "customer_name", "city", "signup_date"],
           list(CUSTOMERS) + list(CUSTOMERS_EXTRA))
    _write(out_dir / "employees_SAMPLE.csv",
           ["employee_id", "employee_name", "role", "manager_id"],
           list(EMPLOYEES))
    _write(out_dir / "returns_SAMPLE.csv",
           ["return_id", "order_id", "product_id", "qty_returned",
            "reason"],
           list(RETURNS))
    _write(out_dir / "price_history_SAMPLE.csv",
           ["product_id", "effective_from", "price_pkr"],
           list(PRICE_HISTORY))

    # Monthly extracts: the 52 clean lines, split by their order's
    # month. Line 22 is duplicated into the April file on purpose.
    order_month = {oid: d[:7] for oid, _, d in ORDERS}
    by_month = {f"2026-0{m}": [] for m in range(1, 7)}
    for line in ORDER_ITEMS:
        by_month[order_month[line[1]]].append(line)
    for month, lines in by_month.items():
        rows = [(lid, oid, pid, qty, price, order_month[oid])
                for lid, oid, pid, qty, price in lines]
        if month == "2026-04":
            lid, oid, pid, qty, price = next(
                line for line in ORDER_ITEMS
                if line[0] == DUPLICATE_LINE_IN_APRIL)
            rows.append((lid, oid, pid, qty, price, order_month[oid]))
            rows.sort(key=lambda r: r[0])
        _write(out_dir / "monthly" / f"orders_{month}_SAMPLE.csv",
               ["line_id", "order_id", "product_id", "quantity",
                "unit_price_pkr", "order_date"],
               rows)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--out-dir", default=str(DEFAULT_OUT))
    args = ap.parse_args()
    main(args.out_dir)

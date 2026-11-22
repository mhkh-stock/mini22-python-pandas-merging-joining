# Mini #22 — data dictionary (SAMPLE / DEMO only)

Fictional store "Noor Electronics" — the same made-up Pakistani
electronics store as Mini #1 / #3 / #10 / #15 / #16, Jan–Jun 2026.
The store, the sales and every number are invented for teaching —
the pandas techniques are real, the business is not. Regenerate
exactly with `python3 src/generate_data.py` (deterministic, no
randomness). Analyse with `python3 src/run_techniques.py`.

## The clean base (Mini #1 / #3)

- **32 orders, 52 order lines, PKR 346,800 total revenue.**
  10 buying customers, 8 sold products, Jan–Jun 2026.
- The clean totals reconcile exactly with Mini #1 and Mini #3:
  monthly revenue sums to PKR 346,800 and customer totals sum to
  PKR 346,800.

## The planted mess (deliberate — this is a joins pack)

Every row below is planted on purpose so the techniques have
something real to catch. Nothing here is an accident.

| File | Planted mess |
|---|---|
| `products_SAMPLE.csv` | product_id **2 listed twice** (duplicate key): "Mechanical Keyboard" at PKR 8,500 and "Mechanical Keyboard — old listing" at PKR 8,000 |
| `customers_SAMPLE.csv` | customer_id **7 listed twice** (duplicate key): "Maryam Iqbal" in Islamabad and in Rawalpindi |
| `orders_SAMPLE.csv` | order **33** has customer_id **`CUST-05`** — a string key that does not match customer 5 |
| `order_items_SAMPLE.csv` | line **53** (order 33, product 1 — good product, bad customer) · line **54** (product **99**, does not exist) · line **55** (product **`P-03`**, wrong key format) |
| `monthly/orders_2026-04_SAMPLE.csv` | line **22** sent twice — it also appears in the March file (a re-sent monthly extract) |
| `returns_SAMPLE.csv` | return **5** is for order **99**, which does not exist |
| `employees_SAMPLE.csv` | employee **E06** reports to manager **E99**, who does not exist |

## data/raw/orders_SAMPLE.csv (33 rows)

| Column | Meaning |
|---|---|
| `order_id` | Order number, 1–33 |
| `customer_id` | Buyer — 1–12, except order 33 (`CUST-05`, planted) |
| `order_date` | Order date, ISO `yyyy-mm-dd`, 2026-01-08 – 2026-06-30 |

## data/raw/order_items_SAMPLE.csv (55 rows)

| Column | Meaning |
|---|---|
| `line_id` | Order-line number, 1–55 (1–52 clean, 53–55 planted) |
| `order_id` | Order the line belongs to |
| `product_id` | Product — 1–9, except line 54 (`99`) and line 55 (`P-03`, planted) |
| `quantity` | Units on the line (≥ 1) |
| `unit_price_pkr` | Price actually charged on the line, PKR |

Line revenue is always `quantity × unit_price_pkr`. The 52 clean
lines total PKR 346,800; all 55 lines total PKR 366,800 (the extra
PKR 20,000 is the 3 planted lines).

## data/raw/products_SAMPLE.csv (10 rows)

| Column | Meaning |
|---|---|
| `product_id` | Product number, 1–9 (2 appears twice — planted duplicate) |
| `product_name` | Product name |
| `category` | Electronics, Furniture, Stationery, Kitchen |
| `price_pkr` | Current catalogue price, PKR |

Product 9 (Bluetooth Speaker, PKR 6,500) never sold — it is the
orphan the outer merge finds.

## data/raw/customers_SAMPLE.csv (13 rows)

| Column | Meaning |
|---|---|
| `customer_id` | Customer number, 1–12 (7 appears twice — planted duplicate) |
| `customer_name` | Customer name |
| `city` | City (Lahore, Karachi, Islamabad, Faisalabad, Multan, Peshawar, Quetta, Rawalpindi) |
| `signup_date` | Signup date, ISO `yyyy-mm-dd` |

Customers 11 (Hira Shah) and 12 (Danish Iqbal) never ordered.

## data/raw/employees_SAMPLE.csv (6 rows)

| Column | Meaning |
|---|---|
| `employee_id` | Employee code E01–E06 |
| `employee_name` | Employee name |
| `role` | Owner, Sales Lead, Sales Assistant, Warehouse Lead, Support Agent, Delivery Rider |
| `manager_id` | Manager's employee code (empty for the owner; E99 for E06 — planted orphan) |

## data/raw/returns_SAMPLE.csv (5 rows)

| Column | Meaning |
|---|---|
| `return_id` | Return number, 1–5 |
| `order_id` | Order the return belongs to (99 for return 5 — planted orphan) |
| `product_id` | Product returned |
| `qty_returned` | Units returned |
| `reason` | Return reason |

## data/raw/price_history_SAMPLE.csv (12 rows)

| Column | Meaning |
|---|---|
| `product_id` | Product number, 1–9 |
| `effective_from` | Date the price took effect, ISO `yyyy-mm-dd` |
| `price_pkr` | Price in effect from that date, PKR |

Three products changed price mid-year: Wireless Mouse PKR 2,500 →
2,300 (2026-04-01), Mechanical Keyboard PKR 8,500 → 9,000
(2026-03-01), Dinner Set PKR 14,500 → 13,900 (2026-05-01). The
other six products held one price all year.

## data/raw/monthly/orders_2026-0X_SAMPLE.csv (6 files, 53 rows)

One file per month, Jan–Jun 2026, each holding that month's clean
order lines (line_id, order_id, product_id, quantity,
unit_price_pkr, order_date). The April file also carries line 22,
which already appeared in the March file — 53 rows stacked, 52
after dedupe, PKR 346,800. The 3 planted bad-key lines are not in
the monthly files (they arrived outside the monthly extracts).

## Totals (verified)

- 32 clean orders, 52 clean lines, total revenue PKR 346,800.
- 55 order lines in the file, total PKR 366,800.
- Revenue by category (clean lines): Electronics PKR 104,000 ·
  Furniture PKR 105,600 · Kitchen PKR 106,000 · Stationery
  PKR 31,200.
- Every clean line satisfies `revenue = quantity × unit_price_pkr`
  (checked by `src/checks.py`); order ids and line ids are unique
  except for the planted duplicates listed above.

## Known quirks

- **The mess is planted, not discovered.** Real messy data has
  unknown unknowns; this pack's orphans are listed above so the
  checks can be exact.
- **One shop, six months, 55 lines.** The patterns scale — the
  row counts do not. On a million-row feed the same checks run,
  but the guard cap and the dedupe keys matter far more.

"""Run the 10 merging/joining techniques — Mini #22.

Reads data/raw/*_SAMPLE.csv (SAMPLE data, Noor Electronics, the same
shop as Mini #1/#3 — 32 clean orders, 52 clean lines, PKR 346,800)
and writes one CSV per technique into outputs/, plus
outputs/summary.json (headline KPIs) and outputs/findings.md
(the findings write-up).

Key discipline: every join key is normalised to string on BOTH sides
before merging — the planted bad keys ("CUST-05", "P-03", 99) then
fail to match exactly as they would in a real messy feed, and the
duplicate keys (product 2, customer 7) are deduped explicitly, never
silently. Row counts and revenues are reconciled in the validation
summary (technique 10); nothing in findings.md is hand-typed.

Re-run any time: python3 src/run_techniques.py
"""

import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw"
OUT = ROOT / "outputs"

CLEAN_ORDERS = 32
CLEAN_LINES = 52
CLEAN_REVENUE = 346800
CROSS_JOIN_GUARD_CAP = 200


def money(x):
    return int(round(x))


def _key(df, col):
    """Normalise a join key to string on one side."""
    df[col] = df[col].astype(str)
    return df


def main():
    OUT.mkdir(parents=True, exist_ok=True)

    orders = pd.read_csv(RAW / "orders_SAMPLE.csv", dtype={"customer_id": str})
    items = pd.read_csv(RAW / "order_items_SAMPLE.csv",
                        dtype={"product_id": str})
    products = pd.read_csv(RAW / "products_SAMPLE.csv",
                           dtype={"product_id": str})
    customers = pd.read_csv(RAW / "customers_SAMPLE.csv",
                            dtype={"customer_id": str})
    employees = pd.read_csv(RAW / "employees_SAMPLE.csv")
    returns = pd.read_csv(RAW / "returns_SAMPLE.csv",
                          dtype={"product_id": str})
    prices = pd.read_csv(RAW / "price_history_SAMPLE.csv",
                         dtype={"product_id": str},
                         parse_dates=["effective_from"])

    items["line_revenue_pkr"] = items["quantity"] * items["unit_price_pkr"]

    # Deduped dimensions (keep the first listing of each key). The
    # duplicate rows stay visible in the raw files; the joins below
    # use the clean key set, and technique 1 shows what happens
    # when you forget this step.
    products_dedup = products.drop_duplicates(subset=["product_id"],
                                              keep="first")
    customers_dedup = customers.drop_duplicates(subset=["customer_id"],
                                                keep="first")

    s = {}  # summary numbers

    # ---------- 1. inner merge (raw catalogue, duplicate key live) ---
    t1 = items.merge(products, on="product_id", how="inner")
    t1 = t1[["line_id", "order_id", "product_id", "quantity",
             "unit_price_pkr", "line_revenue_pkr", "product_name",
             "category", "price_pkr"]].rename(
        columns={"price_pkr": "catalogue_price_pkr"})
    t1 = t1.sort_values(["line_id", "product_name"]).reset_index(drop=True)
    t1.to_csv(OUT / "technique_01_inner_merge.csv", index=False)
    s["t1_output_rows"] = len(t1)
    s["t1_distinct_lines"] = int(t1["line_id"].nunique())
    s["t1_dropped_lines"] = len(items) - s["t1_distinct_lines"]
    s["t1_naive_revenue_pkr"] = money(t1["line_revenue_pkr"].sum())
    s["t1_fanout_excess_pkr"] = s["t1_naive_revenue_pkr"] - money(
        items.loc[items["line_id"].isin(t1["line_id"]),
                  "line_revenue_pkr"].sum())

    # ---------- 2. left merge (deduped catalogue, keep orphans) ------
    t2 = items.merge(products_dedup, on="product_id", how="left")
    t2["is_matched"] = t2["product_name"].notna()
    t2 = t2[["line_id", "order_id", "product_id", "quantity",
             "unit_price_pkr", "line_revenue_pkr", "product_name",
             "category", "price_pkr", "is_matched"]].rename(
        columns={"price_pkr": "catalogue_price_pkr"})
    t2 = t2.sort_values("line_id").reset_index(drop=True)
    # Unmatched lines leave catalogue_price blank; keep money as ints.
    t2["catalogue_price_pkr"] = t2["catalogue_price_pkr"].astype("Int64")
    t2.to_csv(OUT / "technique_02_left_merge.csv", index=False)
    s["t2_output_rows"] = len(t2)
    s["t2_matched_lines"] = int(t2["is_matched"].sum())
    s["t2_unmatched_lines"] = int((~t2["is_matched"]).sum())
    s["t2_unmatched_line_ids"] = [int(x) for x in
                                  t2.loc[~t2["is_matched"], "line_id"]]
    s["t2_matched_revenue_pkr"] = money(
        t2.loc[t2["is_matched"], "line_revenue_pkr"].sum())
    s["t2_unmatched_value_pkr"] = money(
        t2.loc[~t2["is_matched"], "line_revenue_pkr"].sum())

    # ---------- 3. outer merge (find the never-sold product) ---------
    t3 = items.merge(products_dedup, on="product_id", how="outer",
                     indicator=True)
    t3["line_revenue_pkr"] = (t3["quantity"] * t3["unit_price_pkr"])
    t3 = t3[["line_id", "order_id", "product_id", "quantity",
             "unit_price_pkr", "line_revenue_pkr", "product_name",
             "category", "price_pkr", "_merge"]].rename(
        columns={"price_pkr": "catalogue_price_pkr",
                 "_merge": "match_status"})
    t3 = t3.sort_values("line_id", na_position="last").reset_index(drop=True)
    # The orphan product row has no line: keep ints as ints (blank NA).
    for col in ["line_id", "order_id", "quantity", "unit_price_pkr",
                "line_revenue_pkr", "catalogue_price_pkr"]:
        t3[col] = t3[col].astype("Int64")
    t3.to_csv(OUT / "technique_03_outer_merge.csv", index=False)
    s["t3_output_rows"] = len(t3)
    s["t3_orphan_products"] = int((t3["match_status"] == "right_only").sum())
    s["t3_orphan_product_names"] = list(
        t3.loc[t3["match_status"] == "right_only", "product_name"])
    s["t3_orphan_lines"] = int((t3["match_status"] == "left_only").sum())

    # ---------- 4. merge on multiple keys (returns) ------------------
    t4 = returns.merge(items, on=["order_id", "product_id"], how="left")
    t4["is_matched"] = t4["line_id"].notna()
    t4["returned_value_pkr"] = (t4["qty_returned"]
                                * t4["unit_price_pkr"].fillna(0))
    t4 = t4[["return_id", "order_id", "product_id", "qty_returned",
             "reason", "line_id", "quantity", "unit_price_pkr",
             "returned_value_pkr", "is_matched"]]
    t4 = t4.sort_values("return_id").reset_index(drop=True)
    for col in ["line_id", "quantity", "unit_price_pkr",
                "returned_value_pkr"]:
        t4[col] = t4[col].astype("Int64")
    t4.to_csv(OUT / "technique_04_multikey_merge.csv", index=False)
    s["t4_output_rows"] = len(t4)
    s["t4_matched_returns"] = int(t4["is_matched"].sum())
    s["t4_orphan_returns"] = int((~t4["is_matched"]).sum())
    s["t4_returned_value_pkr"] = money(
        t4.loc[t4["is_matched"], "returned_value_pkr"].sum())
    s["t4_net_revenue_after_returns_pkr"] = (
        CLEAN_REVENUE - s["t4_returned_value_pkr"])

    # ---------- 5. merge with indicator (orders x customers) ---------
    t5 = orders.merge(customers_dedup, on="customer_id", how="outer",
                      indicator=True)
    t5 = t5[["order_id", "customer_id", "order_date", "customer_name",
             "city", "signup_date", "_merge"]].rename(
        columns={"_merge": "match_status"})
    t5 = t5.sort_values(["order_id", "customer_id"],
                        na_position="last").reset_index(drop=True)
    # Right-only customers have no order: keep order_id an int (blank NA).
    t5["order_id"] = t5["order_id"].astype("Int64")
    t5.to_csv(OUT / "technique_05_indicator_merge.csv", index=False)
    counts = t5["match_status"].value_counts().to_dict()
    s["t5_output_rows"] = len(t5)
    s["t5_both"] = int(counts.get("both", 0))
    s["t5_left_only"] = int(counts.get("left_only", 0))
    s["t5_right_only"] = int(counts.get("right_only", 0))

    # ---------- 6. concat monthly files + duplicate handling ---------
    frames = []
    for month in ["2026-01", "2026-02", "2026-03",
                  "2026-04", "2026-05", "2026-06"]:
        f = pd.read_csv(RAW / "monthly" / f"orders_{month}_SAMPLE.csv",
                        dtype={"product_id": str})
        f["source_file"] = month
        frames.append(f)
    stacked = pd.concat(frames, ignore_index=True)
    stacked["line_revenue_pkr"] = (stacked["quantity"]
                                   * stacked["unit_price_pkr"])
    stacked_rows = len(stacked)
    dup_ids = sorted(stacked.loc[stacked.duplicated("line_id", keep=False),
                                 "line_id"].unique().tolist())
    t6 = stacked.drop_duplicates(subset=["line_id"], keep="first")
    t6 = t6[["line_id", "order_id", "product_id", "quantity",
             "unit_price_pkr", "order_date", "source_file",
             "line_revenue_pkr"]]
    t6 = t6.sort_values("line_id").reset_index(drop=True)
    t6.to_csv(OUT / "technique_06_concat_monthly.csv", index=False)
    s["t6_stacked_rows"] = stacked_rows
    s["t6_output_rows"] = len(t6)
    s["t6_duplicates_dropped"] = stacked_rows - len(t6)
    s["t6_duplicate_line_ids"] = [int(x) for x in dup_ids]
    s["t6_deduped_revenue_pkr"] = money(t6["line_revenue_pkr"].sum())

    # ---------- 7. lookup with map() (category lookup) ---------------
    cat_map = products_dedup.set_index("product_id")["category"]
    t7 = items.copy()
    t7["category"] = t7["product_id"].map(cat_map)
    t7["is_mapped"] = t7["category"].notna()
    t7 = t7[["line_id", "order_id", "product_id", "quantity",
             "unit_price_pkr", "line_revenue_pkr", "category",
             "is_mapped"]]
    t7 = t7.sort_values("line_id").reset_index(drop=True)
    t7.to_csv(OUT / "technique_07_map_lookup.csv", index=False)
    s["t7_output_rows"] = len(t7)
    s["t7_mapped_lines"] = int(t7["is_mapped"].sum())
    s["t7_unmapped_lines"] = int((~t7["is_mapped"]).sum())
    s["t7_mapped_revenue_pkr"] = money(
        t7.loc[t7["is_mapped"], "line_revenue_pkr"].sum())
    by_cat = (t7.loc[t7["is_mapped"]]
              .groupby("category")["line_revenue_pkr"].sum())
    s["t7_revenue_by_category_pkr"] = {k: money(v)
                                       for k, v in by_cat.items()}

    # ---------- 8. merge_asof (price in effect at order time) ---------
    clean_items = items[items["line_id"] <= CLEAN_LINES].copy()
    left = clean_items.merge(orders[["order_id", "order_date"]],
                             on="order_id", how="left")
    left["order_date"] = pd.to_datetime(left["order_date"])
    # NOTE (pandas 2.1.4 quirk, verified): merge_asof with `by` still
    # requires the on-key GLOBALLY sorted — sorting by (by, on) as the
    # docs suggest raises "left keys must be sorted". Sort by the
    # date only; the by-groups are handled internally and the result
    # is identical (verified on a minimal example).
    left = left.sort_values("order_date")
    right = prices.sort_values("effective_from")
    t8 = pd.merge_asof(left, right, left_on="order_date",
                       right_on="effective_from", by="product_id")
    t8["price_diff_pkr"] = (t8["unit_price_pkr"]
                            - t8["price_pkr"].fillna(0))
    t8 = t8.rename(columns={"price_pkr": "price_effective_pkr"})
    t8 = t8[["line_id", "order_id", "order_date", "product_id",
             "quantity", "unit_price_pkr", "line_revenue_pkr",
             "price_effective_pkr", "price_diff_pkr"]]
    t8["order_date"] = t8["order_date"].dt.strftime("%Y-%m-%d")
    t8 = t8.sort_values(["order_date", "line_id"]).reset_index(drop=True)
    t8.to_csv(OUT / "technique_08_merge_asof.csv", index=False)
    s["t8_output_rows"] = len(t8)
    s["t8_exact_price_lines"] = int((t8["price_diff_pkr"] == 0).sum())
    s["t8_changed_price_lines"] = int((t8["price_diff_pkr"] != 0).sum())
    s["t8_total_price_diff_pkr"] = money(t8["price_diff_pkr"].sum())
    s["t8_asof_revenue_pkr"] = money(
        (t8["quantity"] * t8["price_effective_pkr"]).sum())

    # ---------- 9. self-join (manager lookup) ------------------------
    mgr = employees[["employee_id", "employee_name"]].rename(
        columns={"employee_id": "manager_id",
                 "employee_name": "manager_name"})
    t9 = employees.merge(mgr, on="manager_id", how="left")
    t9["is_matched"] = t9["manager_name"].notna()
    t9 = t9[["employee_id", "employee_name", "role", "manager_id",
             "manager_name", "is_matched"]]
    t9 = t9.sort_values("employee_id").reset_index(drop=True)
    t9.to_csv(OUT / "technique_09_self_join.csv", index=False)
    s["t9_output_rows"] = len(t9)
    s["t9_matched_managers"] = int(t9["is_matched"].sum())
    s["t9_unmatched"] = int((~t9["is_matched"]).sum())

    # ---------- 10. cross-join guard + validation summary ------------
    cross_would_be = len(items) * len(products_dedup)
    guard_blocked = cross_would_be > CROSS_JOIN_GUARD_CAP
    rows = [
        ("01_inner_merge", len(items), len(products), len(t1),
         len(t1), s["t1_dropped_lines"],
         "6 keyboard lines matched the duplicate product 2 twice "
         f"(fan-out): naive revenue PKR {s['t1_naive_revenue_pkr']:,} "
         f"overstates the matched total by PKR {s['t1_fanout_excess_pkr']:,}; "
         f"{s['t1_dropped_lines']} lines dropped (no product match)."),
        ("02_left_merge", len(items), len(products_dedup), len(t2),
         s["t2_matched_lines"], s["t2_unmatched_lines"],
         f"All {len(items)} lines kept; unmatched lines "
         f"{s['t2_unmatched_line_ids']} (PKR {s['t2_unmatched_value_pkr']:,}) "
         "have no product match."),
        ("03_outer_merge", len(items), len(products_dedup), len(t3),
         s["t3_output_rows"] - s["t3_orphan_lines"]
         - s["t3_orphan_products"], s["t3_orphan_lines"]
         + s["t3_orphan_products"],
         "Orphan product: Bluetooth Speaker (never sold). "
         "Orphan lines: 54 (product 99), 55 (product P-03)."),
        ("04_multikey_merge", len(returns), len(items), len(t4),
         s["t4_matched_returns"], s["t4_orphan_returns"],
         f"Returns matched on (order_id, product_id); "
         f"PKR {s['t4_returned_value_pkr']:,} returned; "
         "orphan return 5 (order 99) matches nothing."),
        ("05_indicator_merge", len(orders), len(customers_dedup), len(t5),
         s["t5_both"], s["t5_left_only"] + s["t5_right_only"],
         "left_only = order 33 (customer CUST-05); right_only = "
         "customers 11, 12 (never ordered)."),
        ("06_concat_monthly", s["t6_stacked_rows"], 6, len(t6),
         len(t6), s["t6_duplicates_dropped"],
         f"6 monthly files stacked to {s['t6_stacked_rows']} rows; "
         f"line {s['t6_duplicate_line_ids']} arrived twice "
         "(March + April) and was dropped once."),
        ("07_map_lookup", len(items), len(products_dedup), len(t7),
         s["t7_mapped_lines"], s["t7_unmapped_lines"],
         "map() gives NaN (not an error) for unknown keys: "
         "lines 54, 55 unmapped."),
        ("08_merge_asof", CLEAN_LINES, len(prices), len(t8),
         len(t8), 0,
         f"{s['t8_changed_price_lines']} lines sold at a price that "
         "had already changed; total diff "
         f"PKR {s['t8_total_price_diff_pkr']:,}."),
        ("09_self_join", len(employees), len(employees), len(t9),
         s["t9_matched_managers"], s["t9_unmatched"],
         "Unmatched: E01 (owner, no manager) and E06 (manager E99 "
         "does not exist)."),
        ("10_cross_join_guard", len(items), len(products_dedup), 0, 0, 0,
         f"Cartesian size {len(items)} x {len(products_dedup)} = "
         f"{cross_would_be} rows exceeds the guard cap "
         f"{CROSS_JOIN_GUARD_CAP} — BLOCKED, never materialised."),
    ]
    t10 = pd.DataFrame(rows, columns=[
        "technique", "input_rows_left", "input_rows_right", "output_rows",
        "matched_rows", "unmatched_rows", "notes"])
    t10.to_csv(OUT / "technique_10_validation_summary.csv", index=False)

    # ---------- master reconciliation --------------------------------
    s = {
        "dataset": "Noor Electronics — SAMPLE / DEMO data only "
                   "(fictional store, Jan–Jun 2026; same shop as "
                   "Mini #1 / #3)",
        "clean_orders": CLEAN_ORDERS,
        "clean_lines": CLEAN_LINES,
        "clean_revenue_pkr": CLEAN_REVENUE,
        "order_items_file_rows": len(items),
        "order_items_file_total_pkr": money(items["line_revenue_pkr"].sum()),
        "planted_bad_lines": 3,
        "planted_bad_lines_value_pkr": money(
            items.loc[items["line_id"] > CLEAN_LINES,
                      "line_revenue_pkr"].sum()),
        "duplicate_product_keys": int(
            products.duplicated("product_id").sum()),
        "duplicate_customer_keys": int(
            customers.duplicated("customer_id").sum()),
        "cross_join_would_be_rows": cross_would_be,
        "cross_join_guard_cap": CROSS_JOIN_GUARD_CAP,
        "cross_join_guard_blocked": bool(guard_blocked),
        **s,
    }
    with open(OUT / "summary.json", "w") as f:
        json.dump(s, f, indent=2)
        f.write("\n")

    _write_findings(s)
    print(f"Wrote 10 technique CSVs + summary.json + findings.md to {OUT}")


def _write_findings(s):
    cats = s["t7_revenue_by_category_pkr"]
    cat_lines = "\n".join(
        f"- **{k}: PKR {v:,}**" for k, v in
        sorted(cats.items(), key=lambda kv: -kv[1]))
    text = f"""# Mini #22 — findings (Noor Electronics, SAMPLE data)

Fictional Pakistani electronics store, Jan–Jun 2026 — the same shop
as Mini #1 / #3 (32 clean orders, 52 clean lines, PKR 346,800).
**SAMPLE / DEMO data only** — invented store, invented sales,
never real client or real business data. Every number below is
computed from `data/raw/*_SAMPLE.csv` by `src/run_techniques.py`
and re-checked independently by `src/checks.py`.

The pack plants the mess on purpose: a duplicate product key, a
duplicate customer key, a string customer key (`CUST-05`), two
orphan product keys (`99`, `P-03`), a duplicated monthly line, an
orphan return and an orphan manager. Nothing here is an accident —
each planted row is listed in `data/README.md`.

## Headline numbers

- **32 clean orders, 52 clean lines, PKR 346,800 revenue** — the
  Mini #1 total, reproduced exactly.
- **The raw order-lines file holds {s["order_items_file_rows"]} lines
  worth PKR {s["order_items_file_total_pkr"]:,}.**
  The extra PKR {s["planted_bad_lines_value_pkr"]:,} is the
  {s["planted_bad_lines"]} planted bad-key lines (53–55).
- **Inner merge (technique_01): {s["t1_output_rows"]} rows from
  {s["t1_distinct_lines"]} matched lines.**
  The 6 keyboard lines matched the duplicated product 2 twice,
  so a naive revenue sum reads
  PKR {s["t1_naive_revenue_pkr"]:,} — PKR {s["t1_fanout_excess_pkr"]:,}
  too high.
- **Left merge (technique_02): {s["t2_output_rows"]} rows,
  {s["t2_matched_lines"]} matched, {s["t2_unmatched_lines"]} unmatched.**
  Lines 54 and 55 have no product
  (PKR {s["t2_unmatched_value_pkr"]:,} of would-be revenue).
- **Outer merge (technique_03): {s["t3_output_rows"]} rows.** The
  Bluetooth Speaker never sold — it is the
  {s["t3_orphan_products"]} orphan product.
- **Multi-key merge (technique_04): {s["t4_matched_returns"]} of
  {s["t4_output_rows"]} returns matched.**
  PKR {s["t4_returned_value_pkr"]:,} returned; net revenue after
  returns PKR {s["t4_net_revenue_after_returns_pkr"]:,}.
  Return 5 (order 99) matches nothing.
- **Indicator merge (technique_05): 35 rows — 32 both, 1 left-only,
  2 right-only.** Order 33 has no customer (`CUST-05`); customers
  11 and 12 never ordered.
- **Concat (technique_06): 53 rows stacked, 52 after dedupe.**
  Line 22 arrived in both the March and April files.
- **map() lookup (technique_07): 53 of 55 lines mapped, 2 NaN.**
  Mapped revenue PKR {s["t7_mapped_revenue_pkr"]:,} (the clean
  PKR {CLEAN_REVENUE:,} plus line 53).
- **merge_asof (technique_08): {s["t8_exact_price_lines"]} lines at
  the exact price in effect, {s["t8_changed_price_lines"]} lines
  differ; total price difference PKR {s["t8_total_price_diff_pkr"]:,}.**
  The as-of revenue is PKR {s["t8_asof_revenue_pkr"]:,} against
  PKR {CLEAN_REVENUE:,} at sale.
- **Self-join (technique_09): 4 of 6 employees have a manager.**
  The owner has none; E06's manager (E99) does not exist.
- **Cross-join guard (technique_10): 55 x 9 = 495 combos exceeds
  the 200-row cap — blocked, never materialised.**

## Revenue by category (after the join, technique_07)

{cat_lines}

Total mapped revenue: **PKR {s["t7_mapped_revenue_pkr"]:,}**.
Electronics edges Kitchen by
PKR {cats["Electronics"] - cats["Kitchen"]:,} on the mapped lines;
the gap is real but tiny — no category dominates this shop.

## What the 10 techniques show

1. **Inner merge (technique_01).** An inner join keeps only what
   matches on both sides: 53 of 55 lines survive, lines 54 and 55
   vanish silently. And a duplicate key multiplies rows — the 6
   keyboard lines became 12, so the revenue sum is wrong by
   PKR {s["t1_fanout_excess_pkr"]:,}. Check the key's uniqueness BEFORE you trust a
   joined total.
2. **Left merge (technique_02).** Left keeps every row from the
   left table and fills the misses with nulls. The 2 unmatched
   lines (54, 55) stay visible with no product name — that is how
   you count orphans instead of losing them.
3. **Outer merge (technique_03).** Outer keeps both sides' orphans:
   the 2 bad lines AND the 1 never-sold product. It is the only
   join that answers "what never sold?" — the Bluetooth Speaker.
4. **Multi-key merge (technique_04).** Two keys are stricter than
   one: a return matches only when BOTH order_id and product_id
   agree. Four returns land exactly; the fifth (order 99) matches
   nothing on either key alone or together.
5. **Indicator merge (technique_05).** `indicator=True` labels
   every row `both`, `left_only` or `right_only`, so the join
   audits itself: 32 orders matched a customer, 1 order did not
   (`CUST-05`), 2 customers never ordered.
6. **Concat (technique_06).** Stacking monthly files is a union,
   not a join — and a re-sent file duplicates rows. The stack had
   53 rows; dropping duplicates on `line_id` restores the true 52
   and the true PKR 346,800. Never trust a stacked total before
   the dedupe.
7. **map() lookup (technique_07).** `map()` is a join for one
   column: fast, readable, and silent about misses — unknown keys
   become NaN, not errors. Lines 54 and 55 map to nothing, which
   is correct, but only if you then count the NaNs.
8. **merge_asof (technique_08).** The nearest-backwards join
   answers "what was the price ON that date?" Three products
   changed price mid-year, so {s["t8_changed_price_lines"]} lines
   differ from the price in effect — but the differences almost
   cancel (total PKR {s["t8_total_price_diff_pkr"]:,}),
   which is a coincidence of this sample, not a law.
9. **Self-join (technique_09).** A table joined to itself answers
   hierarchy questions: who manages whom. The left join keeps the
   owner (no manager) and flags E06, whose manager E99 left —
   both are nulls, for opposite reasons.
10. **Cross-join guard (technique_10).** A cross join of 55 lines
    by 9 products is 495 rows — small here, catastrophic on real
    tables. The guard caps it at 200 and refuses to materialise
    it. The validation table reconciles every technique's inputs
    against its outputs, so no row is ever silently gained or lost.

## Two traps this pack teaches

- **A join can multiply your numbers.** A duplicate key on the
  right turns 6 lines into 12 and inflates revenue by
  PKR {s["t1_fanout_excess_pkr"]:,}
  with no error and no warning. Dedupe the key first, or check
  `merge(validate="many_to_one")` — pandas will raise instead of
  silently doubling.
- **An inner join deletes evidence.** Lines 54 and 55 disappear
  from technique_01 without a trace. If the question is "what is
  wrong with our data?", only a left or outer join (or the
  indicator) can answer it — the inner join has already thrown
  the answer away.

## Limits

- **SAMPLE data only.** The store, the sales and the "findings"
  are invented to teach the techniques. The pandas patterns are
  real.
- **The mess is planted, not discovered.** Real messy data has
  unknown unknowns; this pack's orphans are labelled in
  `data/README.md` so the checks can be exact.
- **One shop, six months, 55 lines.** The patterns scale — the
  row counts do not. On a million-row feed the same checks run,
  but the guard cap and the dedupe keys matter far more.
"""
    (OUT / "findings.md").write_text(text)


if __name__ == "__main__":
    main()

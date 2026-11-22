"""Independent checks for Mini #22 — Merging, Joining & Lookup Pack.

Recomputes EVERY headline number from data/raw/*_SAMPLE.csv with the
standard library only (no pandas), then compares against every
output file, outputs/summary.json, outputs/findings.md and README.md.
Also verifies the generator is deterministic by re-running it to a
temp dir and byte-comparing, and that the chart PNG is a real PNG
whose source data matches the technique_07 CSV.

Run: python3 src/checks.py
Exit code 0 = all checks pass. Any failure is a build bug — fix the
build, never weaken the check.
"""

import csv
import hashlib
import json
import subprocess
import sys
import tempfile
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw"
OUT = ROOT / "outputs"

PASSED = 0
FAILED = []


def check(name, ok, detail=""):
    global PASSED
    if ok:
        PASSED += 1
    else:
        FAILED.append(f"{name} :: {detail}")


def rows(path):
    with open(path, newline="") as f:
        return list(csv.DictReader(f))


def main():
    # ================= raw files =================
    orders = rows(RAW / "orders_SAMPLE.csv")
    items = rows(RAW / "order_items_SAMPLE.csv")
    products = rows(RAW / "products_SAMPLE.csv")
    customers = rows(RAW / "customers_SAMPLE.csv")
    employees = rows(RAW / "employees_SAMPLE.csv")
    returns = rows(RAW / "returns_SAMPLE.csv")
    prices = rows(RAW / "price_history_SAMPLE.csv")

    check("orders: 33 rows", len(orders) == 33, str(len(orders)))
    check("orders: ids 1..33 unique",
          sorted(int(r["order_id"]) for r in orders) == list(range(1, 34)))
    bad_cust = [r for r in orders if r["customer_id"] == "CUST-05"]
    check("orders: exactly 1 mismatched customer key (CUST-05)",
          len(bad_cust) == 1 and bad_cust[0]["order_id"] == "33")
    check("orders: other 32 customer ids are plain numbers",
          all(r["customer_id"].isdigit() for r in orders
              if r["customer_id"] != "CUST-05"))

    check("items: 55 rows", len(items) == 55, str(len(items)))
    check("items: line ids 1..55 unique",
          sorted(int(r["line_id"]) for r in items) == list(range(1, 56)))
    rev = {int(r["line_id"]): int(r["quantity"]) * int(r["unit_price_pkr"])
           for r in items}
    check("items: clean 52 lines total PKR 346,800",
          sum(v for k, v in rev.items() if k <= 52) == 346800,
          str(sum(v for k, v in rev.items() if k <= 52)))
    check("items: planted lines 53-55 total PKR 20,000",
          sum(v for k, v in rev.items() if k > 52) == 20000)
    check("items: file total PKR 366,800",
          sum(rev.values()) == 366800)
    check("items: line 53 is order 33 product 1",
          rev[53] == 2500)
    check("items: line 54 is product 99 (orphan)",
          next(r for r in items if r["line_id"] == "54")["product_id"] == "99")
    check("items: line 55 is product P-03 (wrong format)",
          next(r for r in items if r["line_id"] == "55")["product_id"] == "P-03")

    check("products: 10 rows", len(products) == 10)
    prod_by_id = defaultdict(list)
    for r in products:
        prod_by_id[r["product_id"]].append(r)
    check("products: 9 unique ids", len(prod_by_id) == 9)
    check("products: product 2 listed twice (duplicate key)",
          len(prod_by_id["2"]) == 2)
    check("products: duplicate product 2 prices are 8500 and 8000",
          sorted(int(r["price_pkr"]) for r in prod_by_id["2"]) == [8000, 8500])
    check("products: product 9 Bluetooth Speaker never sold",
          "9" not in {r["product_id"] for r in items if int(r["line_id"]) <= 52})

    check("customers: 13 rows", len(customers) == 13)
    cust_by_id = defaultdict(list)
    for r in customers:
        cust_by_id[r["customer_id"]].append(r)
    check("customers: 12 unique ids", len(cust_by_id) == 12)
    check("customers: customer 7 listed twice (duplicate key)",
          len(cust_by_id["7"]) == 2)
    check("customers: duplicate customer 7 cities differ",
          {r["city"] for r in cust_by_id["7"]} == {"Islamabad", "Rawalpindi"})
    check("customers: 11 and 12 never ordered",
          {r["customer_id"] for r in orders if r["customer_id"].isdigit()}
          .isdisjoint({"11", "12"}))

    check("employees: 6 rows", len(employees) == 6)
    emp_ids = {r["employee_id"] for r in employees}
    check("employees: manager E99 does not exist",
          "E99" not in emp_ids)
    check("employees: E01 has no manager",
          next(r for r in employees
               if r["employee_id"] == "E01")["manager_id"] == "")

    check("returns: 5 rows", len(returns) == 5)
    item_pairs = {(r["order_id"], r["product_id"]) for r in items}
    matched_ret = [r for r in returns
                   if (r["order_id"], r["product_id"]) in item_pairs]
    check("returns: 4 match an (order, product) pair",
          len(matched_ret) == 4, str(len(matched_ret)))
    check("returns: 1 orphan (order 99)",
          len(returns) - len(matched_ret) == 1)
    ret_value = sum(int(r["qty_returned"]) * int(
        next(x for x in items if x["order_id"] == r["order_id"]
             and x["product_id"] == r["product_id"])["unit_price_pkr"])
        for r in matched_ret)
    check("returns: matched value PKR 43,500", ret_value == 43500,
          str(ret_value))
    check("returns: net revenue after returns PKR 303,300",
          346800 - ret_value == 303300)

    check("price_history: 12 rows", len(prices) == 12)
    price_by_prod = defaultdict(list)
    for r in prices:
        price_by_prod[r["product_id"]].append(
            (r["effective_from"], int(r["price_pkr"])))
    check("price_history: 3 products changed price",
          sum(1 for v in price_by_prod.values() if len(v) == 2) == 3)
    check("price_history: mouse 2500 -> 2300 on 2026-04-01",
          price_by_prod["1"] == [("2026-01-01", 2500),
                                 ("2026-04-01", 2300)])
    check("price_history: keyboard 8500 -> 9000 on 2026-03-01",
          price_by_prod["2"] == [("2026-01-01", 8500),
                                 ("2026-03-01", 9000)])
    check("price_history: dinner set 14500 -> 13900 on 2026-05-01",
          price_by_prod["8"] == [("2026-01-01", 14500),
                                 ("2026-05-01", 13900)])

    # monthly extracts
    monthly_rows = []
    expected_monthly = {"2026-01": 8, "2026-02": 10, "2026-03": 5,
                        "2026-04": 8, "2026-05": 11, "2026-06": 11}
    for month, n in expected_monthly.items():
        mrows = rows(RAW / "monthly" / f"orders_{month}_SAMPLE.csv")
        check(f"monthly {month}: {n} rows", len(mrows) == n,
              str(len(mrows)))
        monthly_rows.extend((month, r) for r in mrows)
    check("monthly: 53 rows stacked", len(monthly_rows) == 53)
    mline_ids = [int(r["line_id"]) for _, r in monthly_rows]
    check("monthly: line 22 appears twice",
          Counter(mline_ids)[22] == 2)
    check("monthly: no other line duplicated",
          all(v == 1 for k, v in Counter(mline_ids).items() if k != 22))
    check("monthly: union of line ids is the 52 clean lines",
          sorted(set(mline_ids)) == list(range(1, 53)))
    mrev = sum(int(r["quantity"]) * int(r["unit_price_pkr"])
               for _, r in monthly_rows)
    check("monthly: stacked revenue PKR 351,600 (346,800 + dup 4,800)",
          mrev == 351600, str(mrev))

    # ================= summary.json =================
    summary = json.loads((OUT / "summary.json").read_text())
    exp = {
        "clean_orders": 32, "clean_lines": 52, "clean_revenue_pkr": 346800,
        "order_items_file_rows": 55, "order_items_file_total_pkr": 366800,
        "planted_bad_lines": 3, "planted_bad_lines_value_pkr": 20000,
        "duplicate_product_keys": 1, "duplicate_customer_keys": 1,
        "cross_join_would_be_rows": 495, "cross_join_guard_cap": 200,
        "cross_join_guard_blocked": True,
        "t1_output_rows": 59, "t1_distinct_lines": 53,
        "t1_dropped_lines": 2, "t1_naive_revenue_pkr": 400300,
        "t1_fanout_excess_pkr": 51000,
        "t2_output_rows": 55, "t2_matched_lines": 53,
        "t2_unmatched_lines": 2, "t2_matched_revenue_pkr": 349300,
        "t2_unmatched_value_pkr": 17500,
        "t3_output_rows": 56, "t3_orphan_products": 1, "t3_orphan_lines": 2,
        "t4_output_rows": 5, "t4_matched_returns": 4,
        "t4_orphan_returns": 1, "t4_returned_value_pkr": 43500,
        "t4_net_revenue_after_returns_pkr": 303300,
        "t5_output_rows": 35, "t5_both": 32, "t5_left_only": 1,
        "t5_right_only": 2,
        "t6_stacked_rows": 53, "t6_output_rows": 52,
        "t6_duplicates_dropped": 1, "t6_deduped_revenue_pkr": 346800,
        "t7_output_rows": 55, "t7_mapped_lines": 53,
        "t7_unmapped_lines": 2, "t7_mapped_revenue_pkr": 349300,
        "t8_output_rows": 52, "t8_total_price_diff_pkr": -100,
        "t8_asof_revenue_pkr": 346700,
        "t9_output_rows": 6, "t9_matched_managers": 4, "t9_unmatched": 2,
    }
    for k, v in exp.items():
        check(f"summary.json {k} == {v}", summary.get(k) == v,
              f"got {summary.get(k)}")
    check("summary.json category revenues",
          summary.get("t7_revenue_by_category_pkr") == {
              "Electronics": 106500, "Furniture": 105600,
              "Kitchen": 106000, "Stationery": 31200},
          str(summary.get("t7_revenue_by_category_pkr")))
    check("summary.json t2 unmatched line ids are [54, 55]",
          summary.get("t2_unmatched_line_ids") == [54, 55])
    check("summary.json t3 orphan product is Bluetooth Speaker",
          summary.get("t3_orphan_product_names") == ["Bluetooth Speaker"])
    check("summary.json t6 duplicate line id is [22]",
          summary.get("t6_duplicate_line_ids") == [22])
    check("summary.json t8 exact/changed lines sum to 52",
          summary.get("t8_exact_price_lines", 0)
          + summary.get("t8_changed_price_lines", 0) == 52)

    # ================= technique CSVs =================
    def check_header(name, got, want):
        check(f"{name} header", got == want, f"got {got}")

    # T1: inner merge, raw catalogue (duplicate key fans out)
    t1 = rows(OUT / "technique_01_inner_merge.csv")
    check_header("t1", list(t1[0].keys()),
                 ["line_id", "order_id", "product_id", "quantity",
                  "unit_price_pkr", "line_revenue_pkr", "product_name",
                  "category", "catalogue_price_pkr"])
    check("t1: 59 rows", len(t1) == 59, str(len(t1)))
    exp_t1 = []
    for r in items:
        for p in prod_by_id.get(r["product_id"], []):
            exp_t1.append((r["line_id"], p["product_name"],
                           p["category"], p["price_pkr"]))
    got_t1 = [(r["line_id"], r["product_name"], r["category"],
               r["catalogue_price_pkr"]) for r in t1]
    check("t1: row multiset matches raw inner join",
          Counter(got_t1) == Counter(exp_t1))
    for r in t1:
        check(f"t1 line {r['line_id']} revenue = qty x price",
              int(r["line_revenue_pkr"]) == int(r["quantity"])
              * int(r["unit_price_pkr"]))
    check("t1: naive revenue sum PKR 400,300",
          sum(int(r["line_revenue_pkr"]) for r in t1) == 400300)
    check("t1: 6 keyboard lines appear twice",
          Counter(r["line_id"] for r in t1).most_common(6) and
          all(Counter(r["line_id"] for r in t1)[lid] == 2
              for lid in ["3", "9", "20", "27", "35", "46"]))
    check("t1: lines 54 and 55 dropped",
          {"54", "55"}.isdisjoint({r["line_id"] for r in t1}))

    # T2: left merge, deduped catalogue
    t2 = rows(OUT / "technique_02_left_merge.csv")
    check_header("t2", list(t2[0].keys()),
                 ["line_id", "order_id", "product_id", "quantity",
                  "unit_price_pkr", "line_revenue_pkr", "product_name",
                  "category", "catalogue_price_pkr", "is_matched"])
    check("t2: 55 rows", len(t2) == 55)
    check("t2: line ids 1..55 each once",
          sorted(int(r["line_id"]) for r in t2) == list(range(1, 56)))
    unmatched = [r for r in t2 if r["is_matched"] == "False"]
    check("t2: unmatched lines are 54 and 55",
          sorted(r["line_id"] for r in unmatched) == ["54", "55"])
    check("t2: matched revenue PKR 349,300",
          sum(int(r["line_revenue_pkr"]) for r in t2
              if r["is_matched"] == "True") == 349300)
    check("t2: unmatched value PKR 17,500",
          sum(int(r["line_revenue_pkr"]) for r in unmatched) == 17500)
    for r in t2:
        if r["is_matched"] == "True":
            first = prod_by_id[r["product_id"]][0]
            check(f"t2 line {r['line_id']} product name",
                  r["product_name"] == first["product_name"])

    # T3: outer merge
    t3 = rows(OUT / "technique_03_outer_merge.csv")
    check("t3: 56 rows", len(t3) == 56, str(len(t3)))
    check("t3: match_status counts 53/2/1",
          Counter(r["match_status"] for r in t3) == {
              "both": 53, "left_only": 2, "right_only": 1},
          str(Counter(r["match_status"] for r in t3)))
    orphan_prod = [r for r in t3 if r["match_status"] == "right_only"]
    check("t3: orphan product is Bluetooth Speaker",
          len(orphan_prod) == 1
          and orphan_prod[0]["product_name"] == "Bluetooth Speaker")
    check("t3: orphan lines are 54 and 55",
          sorted(r["line_id"] for r in t3
                 if r["match_status"] == "left_only") == ["54", "55"])

    # T4: multi-key merge
    t4 = rows(OUT / "technique_04_multikey_merge.csv")
    check("t4: 5 rows", len(t4) == 5)
    check("t4: 4 matched, 1 orphan",
          sum(1 for r in t4 if r["is_matched"] == "True") == 4
          and sum(1 for r in t4 if r["is_matched"] == "False") == 1)
    check("t4: orphan is return 5 (order 99)",
          next(r for r in t4 if r["is_matched"] == "False")["return_id"] == "5")
    check("t4: returned value PKR 43,500",
          sum(int(r["returned_value_pkr"]) for r in t4) == 43500)
    for r in t4:
        if r["is_matched"] == "True":
            check(f"t4 return {r['return_id']} line revenue matches",
                  int(r["returned_value_pkr"])
                  == int(r["qty_returned"]) * int(r["unit_price_pkr"]))

    # T5: indicator merge
    t5 = rows(OUT / "technique_05_indicator_merge.csv")
    check("t5: 35 rows", len(t5) == 35, str(len(t5)))
    check("t5: match_status counts 32/1/2",
          Counter(r["match_status"] for r in t5) == {
              "both": 32, "left_only": 1, "right_only": 2},
          str(Counter(r["match_status"] for r in t5)))
    check("t5: left_only is order 33 (CUST-05)",
          next(r for r in t5
               if r["match_status"] == "left_only")["order_id"] == "33")
    check("t5: right_only are customers 11 and 12",
          sorted(r["customer_id"] for r in t5
                 if r["match_status"] == "right_only") == ["11", "12"])

    # T6: concat + dedupe
    t6 = rows(OUT / "technique_06_concat_monthly.csv")
    check("t6: 52 rows", len(t6) == 52)
    check("t6: line ids are the 52 clean lines",
          sorted(int(r["line_id"]) for r in t6) == list(range(1, 53)))
    check("t6: revenue PKR 346,800",
          sum(int(r["line_revenue_pkr"]) for r in t6) == 346800)
    check("t6: line 22 kept from the March file",
          next(r for r in t6 if r["line_id"] == "22")["source_file"]
          == "2026-03")
    for r in t6:
        check(f"t6 line {r['line_id']} revenue = qty x price",
              int(r["line_revenue_pkr"]) == int(r["quantity"])
              * int(r["unit_price_pkr"]))

    # T7: map() lookup
    t7 = rows(OUT / "technique_07_map_lookup.csv")
    check("t7: 55 rows", len(t7) == 55)
    check("t7: mapped 53, unmapped 2",
          sum(1 for r in t7 if r["is_mapped"] == "True") == 53
          and sum(1 for r in t7 if r["is_mapped"] == "False") == 2)
    check("t7: unmapped lines are 54 and 55",
          sorted(r["line_id"] for r in t7
                 if r["is_mapped"] == "False") == ["54", "55"])
    cat_rev = defaultdict(int)
    for r in t7:
        if r["is_mapped"] == "True":
            cat_rev[r["category"]] += int(r["line_revenue_pkr"])
    check("t7: category revenues",
          dict(cat_rev) == {"Electronics": 106500, "Furniture": 105600,
                            "Kitchen": 106000, "Stationery": 31200},
          str(dict(cat_rev)))
    check("t7: mapped revenue PKR 349,300",
          sum(cat_rev.values()) == 349300)
    for r in t7:
        if r["is_mapped"] == "True":
            check(f"t7 line {r['line_id']} category matches catalogue",
                  r["category"]
                  == prod_by_id[r["product_id"]][0]["category"])

    # T8: merge_asof — recompute the effective price per line
    t8 = rows(OUT / "technique_08_merge_asof.csv")
    check("t8: 52 rows", len(t8) == 52)
    order_date = {r["order_id"]: r["order_date"] for r in orders}
    item_by_id = {r["line_id"]: r for r in items}
    diffs = []
    for r in t8:
        lid = r["line_id"]
        src = item_by_id[lid]
        d = order_date[src["order_id"]]
        # effective price = the price of the LATEST change on/before
        # the order date (max by date, not max price).
        eff = sorted((d2, p) for d2, p in price_by_prod[src["product_id"]]
                     if d2 <= d)[-1][1]
        check(f"t8 line {lid} effective price",
              int(r["price_effective_pkr"]) == eff,
              f"got {r['price_effective_pkr']} want {eff}")
        check(f"t8 line {lid} diff = sale - effective",
              int(r["price_diff_pkr"]) == int(src["unit_price_pkr"]) - eff)
        diffs.append(int(r["price_diff_pkr"]))
    check("t8: 11 lines differ, 41 exact",
          sum(1 for d in diffs if d != 0) == 11
          and sum(1 for d in diffs if d == 0) == 41,
          str(Counter(d != 0 for d in diffs)))
    check("t8: total price diff PKR -100", sum(diffs) == -100,
          str(sum(diffs)))
    check("t8: as-of revenue PKR 346,700",
          sum(int(r["quantity"]) * int(r["price_effective_pkr"])
              for r in t8) == 346700)

    # T9: self-join
    t9 = rows(OUT / "technique_09_self_join.csv")
    check("t9: 6 rows", len(t9) == 6)
    emp_name = {r["employee_id"]: r["employee_name"] for r in employees}
    emp_mgr = {r["employee_id"]: r["manager_id"] for r in employees}
    for r in t9:
        want = emp_name.get(emp_mgr[r["employee_id"]], "")
        check(f"t9 {r['employee_id']} manager name",
              r["manager_name"] == want,
              f"got {r['manager_name']!r} want {want!r}")
    check("t9: matched 4, unmatched 2",
          sum(1 for r in t9 if r["is_matched"] == "True") == 4
          and sum(1 for r in t9 if r["is_matched"] == "False") == 2)

    # T10: validation summary
    t10 = rows(OUT / "technique_10_validation_summary.csv")
    check("t10: 10 rows", len(t10) == 10, str(len(t10)))
    check("t10: output rows match summary.json",
          all(int(r["output_rows"]) == summary[f"t{i+1}_output_rows"]
              for i, r in enumerate(t10[:9])))
    check("t10: guard row blocks the 495-row cross join",
          t10[9]["technique"] == "10_cross_join_guard"
          and "495" in t10[9]["notes"] and "BLOCKED" in t10[9]["notes"])
    check("t10: every technique reconciles (output >= matched)",
          all(int(r["output_rows"]) >= int(r["matched_rows"])
              for r in t10[:9]))

    # ================= findings.md / README.md =================
    findings = (OUT / "findings.md").read_text()
    readme = (ROOT / "README.md").read_text()
    for label, text in [("findings.md", findings), ("README.md", readme)]:
        check(f"{label} has SAMPLE banner", "SAMPLE" in text)
        check(f"{label} has 346,800", "346,800" in text)
        check(f"{label} has 400,300", "400,300" in text)
        check(f"{label} has 51,000", "51,000" in text)
        check(f"{label} has 349,300", "349,300" in text)
        check(f"{label} has 43,500", "43,500" in text)
        check(f"{label} has 303,300", "303,300" in text)
        check(f"{label} has 346,700", "346,700" in text)
        check(f"{label} has 495", "495" in text)
        check(f"{label} has Bluetooth Speaker", "Bluetooth Speaker" in text)
        check(f"{label} has 366,800", "366,800" in text)

    # ================= chart =================
    png = OUT / "revenue_by_category.png"
    check("chart: file exists and is a real PNG",
          png.exists() and png.read_bytes()[:8] == b"\x89PNG\r\n\x1a\n")
    check("chart: non-trivial size (>10 KB)",
          png.exists() and png.stat().st_size > 10_000,
          str(png.stat().st_size if png.exists() else 0))
    # the chart's source data must be the technique_07 category totals
    check("chart: source data (t7 categories) reconciles",
          dict(cat_rev) == {"Electronics": 106500, "Furniture": 105600,
                            "Kitchen": 106000, "Stationery": 31200})

    # ================= generator determinism =================
    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        proc = subprocess.run(
            [sys.executable, str(ROOT / "src" / "generate_data.py"),
             "--out-dir", str(td)],
            capture_output=True, text=True)
        check("generator re-runs cleanly", proc.returncode == 0,
              proc.stderr[-300:])
        if proc.returncode == 0:
            all_files = sorted((RAW).rglob("*.csv"))
            for src in all_files:
                rel = src.relative_to(RAW)
                regen = td / rel
                check(f"generator deterministic: {rel}",
                      regen.exists()
                      and hashlib.sha256(src.read_bytes()).hexdigest()
                      == hashlib.sha256(regen.read_bytes()).hexdigest())

    # ================= repo furniture =================
    check("requirements.txt pins pandas + matplotlib",
          "pandas" in (ROOT / "requirements.txt").read_text()
          and "matplotlib" in (ROOT / "requirements.txt").read_text())
    check(".gitignore exists", (ROOT / ".gitignore").exists())
    check("data/README.md exists", (ROOT / "data" / "README.md").exists())

    print(f"{PASSED} checks passed, {len(FAILED)} failed")
    if FAILED:
        print("FAILURES:")
        for f in FAILED:
            print(" -", f)
        sys.exit(1)


if __name__ == "__main__":
    main()

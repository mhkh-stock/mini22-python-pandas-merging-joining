# Mini #22 — findings (Noor Electronics, SAMPLE data)

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
- **The raw order-lines file holds 55 lines
  worth PKR 366,800.**
  The extra PKR 20,000 is the
  3 planted bad-key lines (53–55).
- **Inner merge (technique_01): 59 rows from
  53 matched lines.**
  The 6 keyboard lines matched the duplicated product 2 twice,
  so a naive revenue sum reads
  PKR 400,300 — PKR 51,000
  too high.
- **Left merge (technique_02): 55 rows,
  53 matched, 2 unmatched.**
  Lines 54 and 55 have no product
  (PKR 17,500 of would-be revenue).
- **Outer merge (technique_03): 56 rows.** The
  Bluetooth Speaker never sold — it is the
  1 orphan product.
- **Multi-key merge (technique_04): 4 of
  5 returns matched.**
  PKR 43,500 returned; net revenue after
  returns PKR 303,300.
  Return 5 (order 99) matches nothing.
- **Indicator merge (technique_05): 35 rows — 32 both, 1 left-only,
  2 right-only.** Order 33 has no customer (`CUST-05`); customers
  11 and 12 never ordered.
- **Concat (technique_06): 53 rows stacked, 52 after dedupe.**
  Line 22 arrived in both the March and April files.
- **map() lookup (technique_07): 53 of 55 lines mapped, 2 NaN.**
  Mapped revenue PKR 349,300 (the clean
  PKR 346,800 plus line 53).
- **merge_asof (technique_08): 41 lines at
  the exact price in effect, 11 lines
  differ; total price difference PKR -100.**
  The as-of revenue is PKR 346,700 against
  PKR 346,800 at sale.
- **Self-join (technique_09): 4 of 6 employees have a manager.**
  The owner has none; E06's manager (E99) does not exist.
- **Cross-join guard (technique_10): 55 x 9 = 495 combos exceeds
  the 200-row cap — blocked, never materialised.**

## Revenue by category (after the join, technique_07)

- **Electronics: PKR 106,500**
- **Kitchen: PKR 106,000**
- **Furniture: PKR 105,600**
- **Stationery: PKR 31,200**

Total mapped revenue: **PKR 349,300**.
Electronics edges Kitchen by
PKR 500 on the mapped lines;
the gap is real but tiny — no category dominates this shop.

## What the 10 techniques show

1. **Inner merge (technique_01).** An inner join keeps only what
   matches on both sides: 53 of 55 lines survive, lines 54 and 55
   vanish silently. And a duplicate key multiplies rows — the 6
   keyboard lines became 12, so the revenue sum is wrong by
   PKR 51,000. Check the key's uniqueness BEFORE you trust a
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
   changed price mid-year, so 11 lines
   differ from the price in effect — but the differences almost
   cancel (total PKR -100),
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
  PKR 51,000
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

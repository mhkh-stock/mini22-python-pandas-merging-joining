"""Build outputs/revenue_by_category.png — Mini #22.

Left panel: revenue by category after the join (technique_07,
matched lines only). Right panel: matched vs unmatched order lines
(technique_02). Both panels read the technique CSVs, so the chart
can only show numbers the joins actually produced.

Re-run any time: python3 src/build_chart.py
"""

from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "outputs"


def main():
    t7 = pd.read_csv(OUT / "technique_07_map_lookup.csv")
    t2 = pd.read_csv(OUT / "technique_02_left_merge.csv")
    assert len(t7) == 55 and len(t2) == 55

    by_cat = (t7[t7["is_mapped"]]
              .groupby("category")["line_revenue_pkr"].sum()
              .sort_values(ascending=True))
    matched = int(t2["is_matched"].sum())
    unmatched = int((~t2["is_matched"]).sum())

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 5))
    fig.suptitle("Noor Electronics — revenue by category after the join\n"
                 "SAMPLE data, Jan–Jun 2026 (matched lines only)",
                 fontsize=12)

    colors = ["#7fb3d5", "#5dade2", "#2e86c1", "#1a5276"]
    ax1.barh(by_cat.index, by_cat.values / 1000, color=colors)
    for i, v in enumerate(by_cat.values):
        ax1.text(v / 1000 + 2, i, f"PKR {v:,}", va="center", fontsize=9)
    ax1.set_xlabel("Revenue (PKR thousands)")
    ax1.set_title("Revenue by category (joined)")
    ax1.grid(axis="x", alpha=0.3)

    ax2.bar(["Matched", "Unmatched"], [matched, unmatched],
            color=["#2e86c1", "#c0392b"])
    for i, v in enumerate([matched, unmatched]):
        ax2.text(i, v + 1, str(v), ha="center", fontsize=11)
    ax2.set_ylabel("Order lines")
    ax2.set_title("Left merge: lines with / without a product")
    ax2.set_ylim(0, 60)
    ax2.grid(axis="y", alpha=0.3)

    fig.tight_layout(rect=[0, 0, 1, 0.93])
    path = OUT / "revenue_by_category.png"
    fig.savefig(path, dpi=150)
    print(f"Wrote {path}")


if __name__ == "__main__":
    main()

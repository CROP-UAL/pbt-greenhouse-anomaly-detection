"""Generate the RQ2 counterexample failure-mode composition figure.

This script reads only the completed post-hoc CSV:
counterexample_failure_modes_by_property.csv
"""

from __future__ import annotations

import os
from pathlib import Path

Path("/tmp/matplotlib-pbt-campaign").mkdir(parents=True, exist_ok=True)
Path("/tmp/fontconfig-pbt-campaign").mkdir(parents=True, exist_ok=True)
os.environ.setdefault("MPLBACKEND", "Agg")
os.environ.setdefault("MPLCONFIGDIR", "/tmp/matplotlib-pbt-campaign")
os.environ.setdefault("XDG_CACHE_HOME", "/tmp/fontconfig-pbt-campaign")

import matplotlib.pyplot as plt
import pandas as pd


BASE_DIR = Path(__file__).resolve().parent
INPUT = BASE_DIR / "counterexample_failure_modes_by_property.csv"
PDF_OUTPUT = BASE_DIR / "rq2_counterexample_failure_modes_by_property.pdf"
PNG_OUTPUT = BASE_DIR / "rq2_counterexample_failure_modes_by_property.png"

PROPERTY_ORDER = ["CA", "CD", "N", "SS"]
MODE_ORDER = ["A_binary_miss", "B_type_mismatch"]
MODE_LABEL = {
    "A_binary_miss": "Binary miss",
    "B_type_mismatch": "Type mismatch",
}


def main() -> None:
    data = pd.read_csv(INPUT)
    data = data.loc[data["property"].isin(PROPERTY_ORDER) & data["failure_mode"].isin(MODE_ORDER)].copy()

    counts = (
        data.pivot(index="property", columns="failure_mode", values="counterexamples")
        .reindex(PROPERTY_ORDER)
        .reindex(columns=MODE_ORDER)
        .fillna(0)
        .astype(int)
    )
    totals = counts.sum(axis=1)
    percentages = counts.div(totals, axis=0) * 100.0

    plt.rcParams.update(
        {
            "font.family": "DejaVu Sans",
            "font.size": 5.4,
            "axes.labelsize": 5.6,
            "xtick.labelsize": 5.4,
            "ytick.labelsize": 5.4,
            "legend.fontsize": 5.4,
            "pdf.fonttype": 42,
            "ps.fonttype": 42,
        }
    )

    fig, ax = plt.subplots(figsize=(3.35, 1.62))

    colors = {
        "A_binary_miss": "#0072B2",  # Okabe-Ito blue
        "B_type_mismatch": "#D55E00",  # Okabe-Ito vermillion
    }

    x = range(len(PROPERTY_ORDER))
    bottom = [0.0] * len(PROPERTY_ORDER)
    for mode in MODE_ORDER:
        values = percentages[mode].to_numpy()
        ax.bar(
            x,
            values,
            bottom=bottom,
            width=0.62,
            color=colors[mode],
            edgecolor="black",
            linewidth=0.45,
            label=MODE_LABEL[mode],
        )
        for idx, value in enumerate(values):
            if value >= 12.0:
                ax.text(
                    idx,
                    bottom[idx] + value / 2.0,
                    f"{value:.1f}%",
                    ha="center",
                    va="center",
                    color="white",
                    fontsize=5.3,
                )
        bottom = [b + v for b, v in zip(bottom, values)]

    for idx, prop in enumerate(PROPERTY_ORDER):
        ax.text(idx, 101.2, f"n={totals[prop]:,}", ha="center", va="bottom", fontsize=5.0)

    ax.set_xticks(list(x))
    ax.set_xticklabels(PROPERTY_ORDER)
    ax.set_ylim(0, 106)
    ax.set_yticks([0, 25, 50, 75, 100])
    ax.set_ylabel("Counterexamples (%)")
    ax.grid(axis="y", color="#d7d7d7", linewidth=0.4, alpha=0.65)
    ax.set_axisbelow(True)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.legend(
        loc="upper center",
        bbox_to_anchor=(0.5, -0.12),
        ncol=2,
        frameon=False,
        handlelength=1.1,
        columnspacing=1.0,
        borderaxespad=0.0,
    )

    fig.tight_layout(pad=0.25)
    fig.savefig(PDF_OUTPUT, bbox_inches="tight")
    fig.savefig(PNG_OUTPUT, dpi=600, bbox_inches="tight")

    print(f"Read: {INPUT}")
    print(counts.to_string())
    print(f"Wrote: {PDF_OUTPUT}")
    print(f"Wrote: {PNG_OUTPUT}")


if __name__ == "__main__":
    main()

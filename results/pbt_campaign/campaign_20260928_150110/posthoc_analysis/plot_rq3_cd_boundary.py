"""Generate the RQ3 Correlation Deviation compact heatmap.

This script reads only rq3_cd_boundary_detail.csv from the completed
post-hoc analysis. It reconstructs the eight predefined CD strata by
grouping the CSV rows by variable pair and reference condition.
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
import numpy as np
import pandas as pd


BASE_DIR = Path(__file__).resolve().parent
INPUT = BASE_DIR / "rq3_cd_boundary_detail.csv"
PDF_OUTPUT = BASE_DIR / "rq3_cd_boundary_detail_heatmap_4x2.pdf"
PNG_OUTPUT = BASE_DIR / "rq3_cd_boundary_detail_heatmap_4x2.png"

EXPECTED_VALUES = {
    ("DGREXT | XGRINT", "above_p75"): 100.0,
    ("DGREXT | XGRINT", "below_p25"): 6.0,
    ("DHEXT | XHINT", "above_p75"): 0.0,
    ("DHEXT | XHINT", "below_p25"): 0.0,
    ("DTEXT | XTINT", "above_p75"): 26.5,
    ("DTEXT | XTINT", "below_p25"): 0.0,
    ("XTINT | XHINT", "above_p75"): 2.5,
    ("XTINT | XHINT", "below_p25"): 28.0,
}


def validate_source(data: pd.DataFrame) -> None:
    totals = {
        "rows": len(data),
        "checks": int(data["checks"].sum()),
        "passes": int(data["passes"].sum()),
        "counterexamples": int(data["counterexamples"].sum()),
    }
    expected = {"rows": 16, "checks": 1600, "passes": 326, "counterexamples": 1274}
    if totals != expected:
        raise SystemExit(f"Unexpected rq3_cd_boundary_detail.csv totals: {totals}; expected {expected}")
    bad = data.loc[data["checks"] != data["passes"] + data["counterexamples"]]
    if not bad.empty:
        raise SystemExit(f"{len(bad)} source rows violate checks = passes + counterexamples")


def reconstruct_strata(data: pd.DataFrame) -> tuple[pd.DataFrame, list[str], list[str]]:
    pair_order_frame = data[["reference_variable", "target_variable"]].drop_duplicates()
    pair_order = [
        f"{row.target_variable} | {row.reference_variable}"
        for row in pair_order_frame.itertuples(index=False)
    ]
    condition_order = list(data["reference_condition"].drop_duplicates())

    grouped = (
        data.assign(pair=lambda d: d["target_variable"] + " | " + d["reference_variable"])
        .groupby(["pair", "reference_variable", "target_variable", "reference_condition"], sort=False, as_index=False)
        .agg(checks=("checks", "sum"), passes=("passes", "sum"), counterexamples=("counterexamples", "sum"))
    )
    grouped["conformance_pct"] = 100.0 * grouped["passes"] / grouped["checks"]
    grouped["pair"] = pd.Categorical(grouped["pair"], categories=pair_order, ordered=True)
    grouped["reference_condition"] = pd.Categorical(grouped["reference_condition"], categories=condition_order, ordered=True)
    grouped = grouped.sort_values(["pair", "reference_condition"]).reset_index(drop=True)

    totals = {
        "rows": len(grouped),
        "checks": int(grouped["checks"].sum()),
        "passes": int(grouped["passes"].sum()),
        "counterexamples": int(grouped["counterexamples"].sum()),
    }
    expected = {"rows": 8, "checks": 1600, "passes": 326, "counterexamples": 1274}
    if totals != expected:
        raise SystemExit(f"Unexpected reconstructed CD totals: {totals}; expected {expected}")
    bad = grouped.loc[grouped["checks"] != grouped["passes"] + grouped["counterexamples"]]
    if not bad.empty:
        raise SystemExit(f"{len(bad)} reconstructed rows violate checks = passes + counterexamples")
    if not grouped["checks"].eq(200).all():
        raise SystemExit("Not all reconstructed CD strata have n=200")

    observed = {
        (str(row.pair), str(row.reference_condition)): round(float(row.conformance_pct), 1)
        for row in grouped.itertuples(index=False)
    }
    if observed != EXPECTED_VALUES:
        raise SystemExit(f"Reconstructed CD values differ from expected values: {observed}")

    return grouped, pair_order, condition_order


def relative_luminance(rgba: tuple[float, float, float, float]) -> float:
    r, g, b, _ = rgba
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def main() -> None:
    data = pd.read_csv(INPUT)
    validate_source(data)
    grouped, pair_order, condition_order = reconstruct_strata(data)

    values = np.zeros((len(pair_order), len(condition_order)), dtype=float)
    for i, pair in enumerate(pair_order):
        for j, condition in enumerate(condition_order):
            row = grouped.loc[
                grouped["pair"].astype(str).eq(pair)
                & grouped["reference_condition"].astype(str).eq(str(condition))
            ]
            if len(row) != 1:
                raise SystemExit(f"Expected one reconstructed row for {(pair, condition)}, found {len(row)}")
            values[i, j] = float(row.iloc[0]["conformance_pct"])

    plt.rcParams.update(
        {
            "font.family": "DejaVu Sans",
            "font.size": 4.8,
            "axes.labelsize": 5.2,
            "xtick.labelsize": 4.9,
            "ytick.labelsize": 4.9,
            "pdf.fonttype": 42,
            "ps.fonttype": 42,
        }
    )

    fig, ax = plt.subplots(figsize=(3.45, 2.05))
    cmap = plt.get_cmap("Blues")
    im = ax.imshow(values, cmap=cmap, vmin=0, vmax=100, aspect="auto")

    ax.set_xticks(np.arange(len(condition_order)))
    ax.set_xticklabels(condition_order)
    ax.set_yticks(np.arange(len(pair_order)))
    ax.set_yticklabels(pair_order)

    ax.set_xticks(np.arange(-0.5, len(condition_order), 1), minor=True)
    ax.set_yticks(np.arange(-0.5, len(pair_order), 1), minor=True)
    ax.grid(which="minor", color="white", linewidth=0.55)
    ax.tick_params(which="minor", bottom=False, left=False)
    ax.tick_params(axis="both", width=0.6, length=2.5, pad=1.5)
    for spine in ax.spines.values():
        spine.set_visible(False)

    norm = im.norm
    for i in range(values.shape[0]):
        for j in range(values.shape[1]):
            color = "black" if relative_luminance(cmap(norm(values[i, j]))) > 0.52 else "white"
            ax.text(j, i, f"{values[i, j]:.1f}%", ha="center", va="center", fontsize=4.8, color=color)

    cbar = fig.colorbar(im, ax=ax, fraction=0.065, pad=0.035)
    cbar.set_label("Conformance (%)", fontsize=5.2)
    cbar.ax.tick_params(labelsize=4.7, width=0.5, length=2.2)
    cbar.set_ticks([0, 25, 50, 75, 100])

    fig.subplots_adjust(left=0.34, right=0.91, top=0.95, bottom=0.16)
    fig.savefig(PDF_OUTPUT, bbox_inches="tight")
    fig.savefig(PNG_OUTPUT, dpi=600, bbox_inches="tight")

    print("Source reconstruction: 16 source rows -> 8 predefined CD strata")
    print(
        f"Validation totals: checks={int(grouped['checks'].sum())}, "
        f"passes={int(grouped['passes'].sum())}, counterexamples={int(grouped['counterexamples'].sum())}"
    )
    print("All reconstructed strata have equal support n=200")
    print("Pair ordering: " + " ; ".join(pair_order))
    print("Column ordering: " + " ; ".join(str(c) for c in condition_order))
    print("Figure size: 3.45 x 2.05 inches")
    print("Recommended insertion: single-column width")
    print(f"Wrote: {PDF_OUTPUT}")
    print(f"Wrote: {PNG_OUTPUT}")


if __name__ == "__main__":
    main()

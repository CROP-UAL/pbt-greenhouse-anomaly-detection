"""Generate the RQ3 Noise behavioural-boundary multipanel figure.

This script reads only rq3_n_boundary_detail.csv from the completed
post-hoc analysis. It does not recompute campaign outcomes.
"""

from __future__ import annotations

import os
from pathlib import Path

Path("/tmp/matplotlib-pbt-ist2026").mkdir(parents=True, exist_ok=True)
Path("/tmp/fontconfig-pbt-ist2026").mkdir(parents=True, exist_ok=True)
os.environ.setdefault("MPLBACKEND", "Agg")
os.environ.setdefault("MPLCONFIGDIR", "/tmp/matplotlib-pbt-ist2026")
os.environ.setdefault("XDG_CACHE_HOME", "/tmp/fontconfig-pbt-ist2026")

import matplotlib.pyplot as plt
import pandas as pd
from matplotlib.lines import Line2D


BASE_DIR = Path(__file__).resolve().parent
INPUT = BASE_DIR / "rq3_n_boundary_detail.csv"
PDF_OUTPUT = BASE_DIR / "rq3_noise_boundary_detail.pdf"
PNG_OUTPUT = BASE_DIR / "rq3_noise_boundary_detail.png"

SENSOR_ORDER = [
    "DCO2EXT",
    "DGREXT",
    "DHEXT",
    "DTEXT",
    "DVEXT",
    "XCO2INT",
    "XGRINT",
    "XHINT",
    "XTINT",
]

STYLE = {
    -1: {"label": "Negative perturbation", "color": "#0072B2", "marker": "o", "linestyle": "-"},
    1: {"label": "Positive perturbation", "color": "#D55E00", "marker": "s", "linestyle": "--"},
}


def validate(data: pd.DataFrame) -> None:
    totals = {
        "rows": len(data),
        "checks": int(data["checks"].sum()),
        "passes": int(data["passes"].sum()),
        "counterexamples": int(data["counterexamples"].sum()),
    }
    expected = {"rows": 75, "checks": 6000, "passes": 5470, "counterexamples": 530}
    if totals != expected:
        raise SystemExit(f"Unexpected rq3_n_boundary_detail.csv totals: {totals}; expected {expected}")
    bad = data.loc[data["checks"] != data["passes"] + data["counterexamples"]]
    if not bad.empty:
        raise SystemExit(f"{len(bad)} rows violate checks = passes + counterexamples")


def main() -> None:
    data = pd.read_csv(INPUT)
    validate(data)

    plt.rcParams.update(
        {
            "font.family": "DejaVu Sans",
            "font.size": 7.0,
            "axes.labelsize": 8.0,
            "axes.titlesize": 7.5,
            "xtick.labelsize": 6.5,
            "ytick.labelsize": 6.5,
            "legend.fontsize": 7.5,
            "pdf.fonttype": 42,
            "ps.fonttype": 42,
        }
    )

    fig, axes = plt.subplots(3, 3, figsize=(7.05, 4.85), sharey=True)
    axes = axes.flatten()

    for ax, sensor in zip(axes, SENSOR_ORDER):
        sensor_data = data.loc[data["sensor"].eq(sensor)].copy()
        for direction in sorted(sensor_data["direction"].unique()):
            g = sensor_data.loc[sensor_data["direction"].eq(direction)].sort_values("magnitude")
            st = STYLE[int(direction)]
            ax.plot(
                g["magnitude"],
                100.0 * g["conformance_rate"],
                color=st["color"],
                marker=st["marker"],
                linestyle=st["linestyle"],
                linewidth=0.9,
                markersize=3.2,
                markeredgewidth=0.5,
                markeredgecolor="black",
            )

        ax.set_title(sensor, pad=2.0)
        ax.set_ylim(0, 103)
        ax.set_yticks([0, 25, 50, 75, 100])
        ax.grid(axis="y", color="#d7d7d7", linewidth=0.35, alpha=0.7)
        ax.set_axisbelow(True)
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        ax.spines["left"].set_linewidth(0.6)
        ax.spines["bottom"].set_linewidth(0.6)
        ax.tick_params(axis="both", width=0.6, length=2.4, pad=1.5)

        mags = sorted(sensor_data["magnitude"].unique())
        ax.set_xticks(mags)
        ax.set_xticklabels([f"{m:g}" for m in mags], rotation=0)

    fig.supxlabel("Perturbation magnitude", y=0.055, fontsize=8.0)
    fig.supylabel("Conformance (%)", x=0.015, fontsize=8.0)

    legend_handles = [
        Line2D(
            [0],
            [0],
            color=STYLE[-1]["color"],
            marker=STYLE[-1]["marker"],
            linestyle=STYLE[-1]["linestyle"],
            linewidth=0.9,
            markersize=3.2,
            markeredgewidth=0.5,
            markeredgecolor="black",
            label=STYLE[-1]["label"],
        ),
        Line2D(
            [0],
            [0],
            color=STYLE[1]["color"],
            marker=STYLE[1]["marker"],
            linestyle=STYLE[1]["linestyle"],
            linewidth=0.9,
            markersize=3.2,
            markeredgewidth=0.5,
            markeredgecolor="black",
            label=STYLE[1]["label"],
        ),
    ]
    fig.legend(
        handles=legend_handles,
        loc="lower center",
        bbox_to_anchor=(0.5, 0.005),
        ncol=2,
        frameon=False,
        handlelength=2.0,
        columnspacing=1.8,
    )

    fig.subplots_adjust(left=0.085, right=0.995, top=0.955, bottom=0.16, wspace=0.24, hspace=0.34)
    fig.savefig(PDF_OUTPUT, bbox_inches="tight")
    fig.savefig(PNG_OUTPUT, dpi=600, bbox_inches="tight")

    print(f"Read: {INPUT}")
    print(
        f"Totals: rows={len(data)}, checks={int(data['checks'].sum())}, "
        f"passes={int(data['passes'].sum())}, counterexamples={int(data['counterexamples'].sum())}"
    )
    print("Figure size: 7.05 x 4.85 inches")
    print("Recommended insertion: double-column width")
    print(f"Wrote: {PDF_OUTPUT}")
    print(f"Wrote: {PNG_OUTPUT}")


if __name__ == "__main__":
    main()

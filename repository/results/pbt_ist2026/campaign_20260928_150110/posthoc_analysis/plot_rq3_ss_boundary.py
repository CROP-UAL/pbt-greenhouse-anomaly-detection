"""Generate the RQ3 Stuck Sensor behavioural-boundary heatmap.

This script reads only rq3_ss_boundary_detail.csv from the completed
post-hoc analysis. It does not recompute campaign outcomes.

The five columns are ordered duration levels because the actual configured
durations are sensor-specific. Each cell reports the observed conformance,
the actual duration value, and the executed support n.
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
import numpy as np
import pandas as pd


BASE_DIR = Path(__file__).resolve().parent
INPUT = BASE_DIR / "rq3_ss_boundary_detail.csv"
PDF_OUTPUT = BASE_DIR / "rq3_ss_boundary_detail_heatmap.pdf"
PNG_OUTPUT = BASE_DIR / "rq3_ss_boundary_detail_heatmap.png"


def validate(data: pd.DataFrame) -> None:
    totals = {
        "rows": len(data),
        "checks": int(data["checks"].sum()),
        "passes": int(data["passes"].sum()),
        "counterexamples": int(data["counterexamples"].sum()),
    }
    expected = {"rows": 40, "checks": 2157, "passes": 1435, "counterexamples": 722}
    if totals != expected:
        raise SystemExit(f"Unexpected rq3_ss_boundary_detail.csv totals: {totals}; expected {expected}")
    bad = data.loc[data["checks"] != data["passes"] + data["counterexamples"]]
    if not bad.empty:
        raise SystemExit(f"{len(bad)} rows violate checks = passes + counterexamples")
    counts = data.groupby("sensor")["duration"].size()
    if not counts.eq(5).all():
        raise SystemExit(f"Expected five duration levels per sensor, found: {counts.to_dict()}")


def relative_luminance(rgba: tuple[float, float, float, float]) -> float:
    r, g, b, _ = rgba
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def main() -> None:
    data = pd.read_csv(INPUT)
    validate(data)

    sensors = list(data["sensor"].drop_duplicates())
    levels = [f"Level {i}" for i in range(1, 6)]

    values = np.zeros((len(sensors), 5), dtype=float)
    durations = np.zeros((len(sensors), 5), dtype=int)
    checks = np.zeros((len(sensors), 5), dtype=int)

    for row_idx, sensor in enumerate(sensors):
        g = data.loc[data["sensor"].eq(sensor)].sort_values("duration").reset_index(drop=True)
        values[row_idx, :] = 100.0 * g["conformance_rate"].to_numpy()
        durations[row_idx, :] = g["duration"].astype(int).to_numpy()
        checks[row_idx, :] = g["checks"].astype(int).to_numpy()

    plt.rcParams.update(
        {
            "font.family": "DejaVu Sans",
            "font.size": 7.0,
            "axes.labelsize": 8.0,
            "xtick.labelsize": 7.0,
            "ytick.labelsize": 7.3,
            "pdf.fonttype": 42,
            "ps.fonttype": 42,
        }
    )

    fig, ax = plt.subplots(figsize=(7.05, 4.65))
    cmap = plt.get_cmap("Blues")
    im = ax.imshow(values, cmap=cmap, vmin=0, vmax=100, aspect="auto")

    ax.set_xticks(np.arange(5))
    ax.set_xticklabels(levels)
    ax.set_yticks(np.arange(len(sensors)))
    ax.set_yticklabels(sensors)
    ax.set_xlabel("Ordered stuck-duration level")
    ax.set_ylabel("Sensor")

    ax.set_xticks(np.arange(-0.5, 5, 1), minor=True)
    ax.set_yticks(np.arange(-0.5, len(sensors), 1), minor=True)
    ax.grid(which="minor", color="white", linewidth=0.55)
    ax.tick_params(which="minor", bottom=False, left=False)
    ax.tick_params(axis="both", width=0.6, length=2.5, pad=1.5)
    for spine in ax.spines.values():
        spine.set_visible(False)

    norm = im.norm
    for i in range(values.shape[0]):
        for j in range(values.shape[1]):
            color = "black" if relative_luminance(cmap(norm(values[i, j]))) > 0.52 else "white"
            label = f"{values[i, j]:.1f}%\nd={durations[i, j]}, n={checks[i, j]}"
            ax.text(j, i, label, ha="center", va="center", fontsize=6.8, color=color, linespacing=1.08)

    cbar = fig.colorbar(im, ax=ax, fraction=0.055, pad=0.025)
    cbar.set_label("Conformance (%)", fontsize=8.0)
    cbar.ax.tick_params(labelsize=6.8, width=0.5, length=2.2)
    cbar.set_ticks([0, 25, 50, 75, 100])

    fig.subplots_adjust(left=0.13, right=0.91, top=0.985, bottom=0.12)
    fig.savefig(PDF_OUTPUT, bbox_inches="tight")
    fig.savefig(PNG_OUTPUT, dpi=600, bbox_inches="tight")

    common_durations = data.groupby("sensor")["duration"].apply(tuple).nunique() == 1
    print(f"Read: {INPUT}")
    print(
        f"Totals: rows={len(data)}, checks={int(data['checks'].sum())}, "
        f"passes={int(data['passes'].sum())}, counterexamples={int(data['counterexamples'].sum())}"
    )
    print(f"All strata represented: {values.size == 40}")
    print(f"Common duration values across sensors: {common_durations}")
    print("Duration representation: ordered Level 1--Level 5 columns; actual duration d shown in each cell")
    print("Figure size: 7.05 x 4.65 inches")
    print("Recommended insertion: double-column width")
    print(f"Wrote: {PDF_OUTPUT}")
    print(f"Wrote: {PNG_OUTPUT}")


if __name__ == "__main__":
    main()

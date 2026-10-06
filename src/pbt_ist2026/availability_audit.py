"""Dry-run availability audit for the PBT campaign.

The audit counts eligible real validation-period base contexts per planned
experimental stratum. It does not generate PBT cases, call the SUT, or modify
any project data.
"""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

try:
    import pandas as pd
except ImportError as exc:  # pragma: no cover - environment guard
    raise SystemExit(
        "pandas is required for the PBT availability audit. "
        "Use the project environment from requirements.txt."
    ) from exc

ROOT = Path(__file__).resolve().parents[2]
PBT_DIR = Path(__file__).resolve().parent
CONFIG_DIR = ROOT / "config"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(PBT_DIR) not in sys.path:
    sys.path.insert(0, str(PBT_DIR))
if str(CONFIG_DIR) not in sys.path:
    sys.path.insert(0, str(CONFIG_DIR))

from pbt_config import (  # noqa: E402
    CA_BASES_PER_CONFIG,
    CA_CO2_DURATIONS,
    CA_CO2_VALUES,
    CA_CONTEXT,
    CA_RADIATION_RATIOS,
    CA_TEMP_DELTAS,
    CD_BASES_PER_CONFIG,
    CD_PAIRS,
    CD_REFERENCE_QUARTILES,
    MV_BASES_PER_SENSOR,
    NOISE_BASES_PER_CONFIG,
    NOISE_DELTAS,
    ORV_ALPHAS,
    ORV_BASES_PER_CONFIG,
    ORV_DIRECTIONS,
    PHYSICAL_RANGES,
    PSF_BASES_PER_SUBSET,
    RANDOM_SEED,
    SENSORS,
    SS_BASE_WINDOWS_PER_CONFIG,
    SS_DURATIONS,
    SS_XGRINT_CONTEXT,
    VALIDATION_START,
    expected_checks,
    five_levels,
    psf_subsets_by_cardinality,
)


def _read_validation_data() -> pd.DataFrame:
    parquet_path = ROOT / "data" / "interim" / "authorized_validation_campaign.parquet"
    if not parquet_path.exists():
        raise SystemExit(
            "Validation dataset not found. Place the authorized parquet file at "
            f"{parquet_path.relative_to(ROOT)} before running the availability audit."
        )
    columns = [
        "Fecha",
        "etiqueta_deteccion",
        "etiqueta_tipo_anomalia",
        *SENSORS,
        "UVENT_cen",
        "UVENT_lN",
    ]
    df = pd.read_parquet(parquet_path, columns=columns)
    df["Fecha"] = pd.to_datetime(df["Fecha"])
    return df.loc[df["Fecha"] >= pd.Timestamp(VALIDATION_START)].sort_values("Fecha").reset_index(drop=True)


def _physical_valid_mask(df: pd.DataFrame, sensors: list[str] | None = None) -> pd.Series:
    sensors = sensors or SENSORS
    mask = pd.Series(True, index=df.index)
    for sensor in sensors:
        lo, hi = PHYSICAL_RANGES[sensor]
        mask &= df[sensor].notna() & df[sensor].between(lo, hi, inclusive="both")
    return mask


def _normal_base_mask(df: pd.DataFrame) -> pd.Series:
    return df["etiqueta_deteccion"].eq("normal") & _physical_valid_mask(df)


def _run_lengths(mask: pd.Series) -> pd.Series:
    groups = mask.ne(mask.shift(fill_value=False)).cumsum()
    lengths = mask.groupby(groups).transform("size")
    return lengths.where(mask, 0)


def _count_candidate_window_starts(mask: pd.Series, duration: int) -> int:
    lengths = _run_lengths(mask)
    # Number of valid window starts in each run is run_length - duration + 1.
    run_ends = mask & ~mask.shift(-1, fill_value=False)
    return int((lengths[run_ends] - duration + 1).clip(lower=0).sum())


def _count_independent_windows(mask: pd.Series, duration: int) -> int:
    lengths = _run_lengths(mask)
    # Independent SS windows are non-overlapping windows within each admissible run.
    run_ends = mask & ~mask.shift(-1, fill_value=False)
    return int((lengths[run_ends] // duration).sum())


def _status(available: int, required: int) -> str:
    return "ok" if available >= required else "insufficient"


def _add(rows: list[dict], prop: str, stratum: str, available: int, required: int, detail: dict | None = None) -> None:
    rows.append(
        {
            "property": prop,
            "stratum": stratum,
            "available_base_contexts": int(available),
            "required_base_contexts": int(required),
            "status": _status(int(available), int(required)),
            "detail": json.dumps(detail or {}, sort_keys=True),
        }
    )


def run_audit() -> tuple[pd.DataFrame, dict]:
    df = _read_validation_data()
    base_mask = _normal_base_mask(df)
    rows: list[dict] = []

    for sensor in SENSORS:
        sensor_mask = base_mask & df[sensor].notna()
        _add(rows, "MV", sensor, sensor_mask.sum(), MV_BASES_PER_SENSOR)

    for sensor, durations in SS_DURATIONS.items():
        sensor_mask = base_mask & df[sensor].notna()
        if sensor == "PRGINT":
            roll_std = df["PRAD"].rolling(
                SS_XGRINT_CONTEXT["rolling_window_samples"],
                min_periods=5,
            ).std()
            sensor_mask &= (
                df["PRGINT"].gt(SS_XGRINT_CONTEXT["PRGINT_min"])
                & df["PRAD"].gt(SS_XGRINT_CONTEXT["PRAD_min"])
                & roll_std.gt(SS_XGRINT_CONTEXT["PRAD_rolling_std_30m_min"])
            )
        for duration in durations:
            available = _count_independent_windows(sensor_mask, duration)
            _add(rows, "SS", f"{sensor}|duration={duration}", available, SS_BASE_WINDOWS_PER_CONFIG)

    for sensor, cfg in NOISE_DELTAS.items():
        sensor_mask = base_mask & df[sensor].notna()
        prev_ok = df[sensor].shift(1).notna()
        next_ok = df[sensor].shift(-1).notna()
        eligible = sensor_mask & prev_ok & next_ok
        for direction in cfg["directions"]:
            for magnitude in five_levels(cfg["min"], cfg["max"]):
                lo, hi = PHYSICAL_RANGES[sensor]
                candidate = df[sensor] + direction * magnitude
                available = (eligible & candidate.between(lo, hi, inclusive="both")).sum()
                _add(
                    rows,
                    "N",
                    f"{sensor}|direction={direction}|magnitude={magnitude:g}",
                    available,
                    NOISE_BASES_PER_CONFIG,
                )

    for sensor in SENSORS:
        for direction in ORV_DIRECTIONS:
            for alpha in ORV_ALPHAS:
                _add(
                    rows,
                    "ORV",
                    f"{sensor}|direction={direction}|alpha={alpha:g}",
                    (base_mask & df[sensor].notna()).sum(),
                    ORV_BASES_PER_CONFIG,
                )

    radiation_mask = (
        base_mask
        & df["PRAD"].gt(CA_CONTEXT["radiation"]["PRAD_min"])
        & (df["PRGINT"] / df["PRAD"]).gt(CA_CONTEXT["radiation"]["normal_ratio_min"])
    )
    for ratio in CA_RADIATION_RATIOS:
        _add(rows, "CA", f"radiation|ratio={ratio:g}", radiation_mask.sum(), CA_BASES_PER_CONFIG)

    vent_cols = [c for c in ("UVENT_cen", "UVENT_lN") if c in df.columns]
    if vent_cols:
        vent_open = df[vent_cols].max(axis=1).ge(CA_CONTEXT["co2_vent"]["vent_open_min"])
    else:
        vent_open = pd.Series(False, index=df.index)
    co2_row_mask = base_mask & vent_open & df["PRAD"].ge(CA_CONTEXT["co2_vent"]["PRAD_min"])
    for co2_value in CA_CO2_VALUES:
        for duration in CA_CO2_DURATIONS:
            _add(
                rows,
                "CA",
                f"co2_vent|co2={co2_value:g}|duration={duration}",
                _count_candidate_window_starts(co2_row_mask, duration),
                CA_BASES_PER_CONFIG,
            )

    temp_mask = (
        base_mask
        & df["PRAD"].gt(CA_CONTEXT["temp_inversion"]["PRAD_min"])
        & df["PTEXT"].gt(CA_CONTEXT["temp_inversion"]["PTEXT_min"])
    )
    for delta in CA_TEMP_DELTAS:
        _add(rows, "CA", f"temp_inversion|delta={delta:g}", temp_mask.sum(), CA_BASES_PER_CONFIG)

    normal_df = df.loc[base_mask, SENSORS].copy()
    for target, reference in CD_PAIRS:
        p25 = normal_df[reference].quantile(0.25)
        p75 = normal_df[reference].quantile(0.75)
        for quartile in CD_REFERENCE_QUARTILES:
            if quartile == "low":
                available = normal_df[reference].lt(p25).sum()
            else:
                available = normal_df[reference].gt(p75).sum()
            _add(
                rows,
                "CD",
                f"{target},{reference}|reference_quartile={quartile}",
                available,
                CD_BASES_PER_CONFIG,
                {"reference_p25": float(p25), "reference_p75": float(p75)},
            )

    complete_base_count = int(base_mask.sum())
    for cardinality, subsets in psf_subsets_by_cardinality().items():
        for subset in subsets:
            _add(
                rows,
                "PSF",
                f"cardinality={cardinality}|subset={'+'.join(subset)}",
                complete_base_count,
                PSF_BASES_PER_SUBSET,
            )

    audit = pd.DataFrame(rows)
    summary = {
        "random_seed": RANDOM_SEED,
        "validation_start": VALIDATION_START,
        "validation_rows": int(len(df)),
        "normal_complete_base_rows": complete_base_count,
        "planned_checks": {x.property_name: x.checks for x in expected_checks()},
        "planned_checks_total": int(sum(x.checks for x in expected_checks())),
        "strata": int(len(audit)),
        "insufficient_strata": int(audit["status"].eq("insufficient").sum()),
    }
    return audit, summary


def write_ss_availability_report(audit: pd.DataFrame) -> Path:
    ss = audit.loc[audit["property"].eq("SS")].copy()
    ss[["implementation_sensor", "duration"]] = ss["stratum"].str.extract(r"([^|]+)\|duration=(\d+)")
    ss["duration"] = ss["duration"].astype(int)

    from pbt_config import PAPER_NAME  # local import keeps the main import list compact

    ss["paper_sensor"] = ss["implementation_sensor"].map(PAPER_NAME)
    ss["requested_base_windows"] = ss["required_base_contexts"]
    ss["available_independent_admissible_windows"] = ss["available_base_contexts"]
    ss["final_planned_checks"] = ss[["requested_base_windows", "available_independent_admissible_windows"]].min(axis=1)
    ss["quota_achieved_pct"] = (
        100.0 * ss["final_planned_checks"] / ss["requested_base_windows"]
    ).round(2)
    ss["insufficient"] = ss["final_planned_checks"].lt(ss["requested_base_windows"])
    ss = ss[
        [
            "paper_sensor",
            "implementation_sensor",
            "duration",
            "requested_base_windows",
            "available_independent_admissible_windows",
            "final_planned_checks",
            "quota_achieved_pct",
            "insufficient",
        ]
    ].sort_values(["implementation_sensor", "duration"])

    out_dir = ROOT / "results" / "pbt_ist2026"
    out_dir.mkdir(parents=True, exist_ok=True)
    ss_path = out_dir / "pbt_ss_availability_report.csv"
    ss.to_csv(ss_path, index=False, quoting=csv.QUOTE_MINIMAL)
    return ss_path


def main() -> None:
    audit, summary = run_audit()
    out_dir = ROOT / "results" / "pbt_ist2026"
    out_dir.mkdir(parents=True, exist_ok=True)
    audit_path = out_dir / "pbt_availability_audit.csv"
    summary_path = out_dir / "pbt_availability_summary.json"
    audit.to_csv(audit_path, index=False, quoting=csv.QUOTE_MINIMAL)
    ss_path = write_ss_availability_report(audit)

    ss = audit.loc[audit["property"].eq("SS")]
    adaptive_ss_total = int(ss[["available_base_contexts", "required_base_contexts"]].min(axis=1).sum())
    fixed = summary["planned_checks"].copy()
    fixed["SS"] = adaptive_ss_total
    summary["planned_checks_adaptive_ss"] = fixed
    summary["planned_checks_total_adaptive_ss"] = int(sum(fixed.values()))
    summary["ss_report_path"] = str(ss_path.relative_to(ROOT))

    summary_path.write_text(json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8")

    print(json.dumps(summary, indent=2, sort_keys=True))
    if summary["insufficient_strata"]:
        print("\nInsufficient strata:")
        print(audit.loc[audit["status"].eq("insufficient")].to_string(index=False))


if __name__ == "__main__":
    main()

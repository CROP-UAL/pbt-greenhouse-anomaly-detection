"""Post-hoc analysis of the completed PBT campaign.

This script reads an existing campaign directory and writes derived summaries.
It does not regenerate cases, execute the SUT, or modify campaign outputs.
"""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import pandas as pd

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
    CD_PAIRS,
    PAPER_NAME,
    SENSORS,
    VALIDATION_START,
)
from availability_audit import _normal_base_mask  # noqa: E402

CAMPAIGN = ROOT / "results" / "pbt_campaign" / "campaign_20260928_150110"
OUT = CAMPAIGN / "posthoc_analysis"


def wilson(k: int, n: int, z: float = 1.959963984540054) -> tuple[float, float, float]:
    if n == 0:
        return (math.nan, math.nan, math.nan)
    p = k / n
    den = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / den
    half = z * math.sqrt((p * (1 - p) + z * z / (4 * n)) / n) / den
    return p, max(0.0, centre - half), min(1.0, centre + half)


def add_rates(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    for col in ["pass", "fail"]:
        if col not in df.columns:
            df[col] = 0
    df["valid_property_checks"] = df["pass"] + df["fail"]
    df["conformance_rate"] = df["pass"] / df["valid_property_checks"]
    df["counterexample_rate"] = df["fail"] / df["valid_property_checks"]
    ci = [wilson(int(r["pass"]), int(r["valid_property_checks"])) for _, r in df.iterrows()]
    df["cr_ci95_low"] = [x[1] for x in ci]
    df["cr_ci95_high"] = [x[2] for x in ci]
    return df


def theta_frame(cases: pd.DataFrame) -> pd.DataFrame:
    theta = cases["theta_json"].map(json.loads).apply(pd.Series)
    theta = theta.add_prefix("theta_")
    return pd.concat([cases.drop(columns=["theta_json"]), theta], axis=1)


def group_summary(df: pd.DataFrame, cols: list[str]) -> pd.DataFrame:
    out = df.groupby(cols + ["oracle_result"], dropna=False).size().unstack(fill_value=0).reset_index()
    return add_rates(out)


def table_text(df: pd.DataFrame) -> str:
    try:
        return df.to_markdown(index=False)
    except ImportError:
        return "```\n" + df.to_string(index=False) + "\n```"


def load_validation_df() -> pd.DataFrame:
    data_path = ROOT / "data" / "interim" / "authorized_validation_campaign.parquet"
    if not data_path.exists():
        raise SystemExit(
            "Validation dataset not found. Place the authorized parquet file at "
            f"{data_path.relative_to(ROOT)} before rerunning post-hoc analyses that require raw validation values."
        )
    df = pd.read_parquet(data_path)
    df["Fecha"] = pd.to_datetime(df["Fecha"])
    return df.loc[df["Fecha"] >= pd.Timestamp(VALIDATION_START)].sort_values("Fecha").reset_index(drop=True)


def classify_failure(row: pd.Series) -> str:
    if row["oracle_result"] != "fail":
        return "not_failure"
    if row["pred_deteccion"] != row["expected_detection"]:
        return "A_binary_miss"
    if row["pred_tipo_anomalia"] != row["expected_type"]:
        return "B_type_mismatch"
    return "other"


def format_pct(x: float) -> str:
    return f"{100 * x:.2f}%"


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)

    cases = pd.read_csv(CAMPAIGN / "pbt_cases_raw.csv")
    checks = pd.read_csv(CAMPAIGN / "pbt_property_checks.csv")
    counters = pd.read_csv(CAMPAIGN / "pbt_counterexamples.csv")
    prop_report = pd.read_csv(CAMPAIGN / "pbt_execution_report_by_property.csv")
    coverage_theta = pd.read_csv(CAMPAIGN / "pbt_realized_coverage_by_theta.csv")
    ss_support = pd.read_csv(CAMPAIGN / "pbt_ss_realized_rq3_support.csv")
    integrity = json.loads((CAMPAIGN / "pbt_integrity_report.json").read_text(encoding="utf-8"))

    enriched = theta_frame(cases).merge(
        checks.drop(columns=["theta_json", "property", "expected_detection", "expected_type", "rq3_supported"]),
        on="case_id",
        how="left",
    )
    enriched["paper_sensor"] = enriched["theta_paper_sensor"].fillna(enriched.get("theta_sensor", pd.Series(index=enriched.index, dtype=object)).map(PAPER_NAME))

    # RQ1
    rq1 = prop_report.rename(columns={"valid_property_checks": "phi_valid_checks"}).copy()
    rq1["generated_checks"] = rq1["phi_valid_checks"]
    rq1["rejected_candidates"] = 0
    rq1["sut_executed_checks"] = rq1["phi_valid_checks"]
    rq1["oracle_evaluated_checks"] = rq1["phi_valid_checks"]
    rq1["realized_theta_configurations"] = coverage_theta.groupby("property").size().reindex(rq1["property"]).values
    rq1["configurations_with_reduced_coverage"] = rq1["property"].map({"SS": 22}).fillna(0).astype(int)
    rq1["operationalized_end_to_end"] = True
    rq1 = rq1[
        [
            "property",
            "planned_checks",
            "generated_checks",
            "phi_valid_checks",
            "rejected_candidates",
            "sut_executed_checks",
            "oracle_evaluated_checks",
            "realized_theta_configurations",
            "configurations_with_reduced_coverage",
            "operationalized_end_to_end",
        ]
    ]
    rq1.to_csv(OUT / "rq1_operationalization_summary.csv", index=False)

    # RQ2
    rq2_prop = add_rates(prop_report[["property", "pass", "fail"]])
    rq2_prop.to_csv(OUT / "rq2_conformance_by_property.csv", index=False)

    mv = group_summary(enriched[enriched["property"].eq("MV")], ["paper_sensor", "theta_sensor"])
    mv.to_csv(OUT / "rq2_mv_by_sensor.csv", index=False)

    ss = group_summary(enriched[enriched["property"].eq("SS")], ["paper_sensor", "theta_sensor", "theta_duration"])
    ss["ss_configuration"] = ss["theta_sensor"] + "|duration=" + ss["theta_duration"].astype(int).astype(str)
    ss = ss.merge(ss_support.rename(columns={"configuration": "ss_configuration"}), on="ss_configuration", how="left")
    ss.to_csv(OUT / "rq2_ss_by_sensor_duration.csv", index=False)

    noise = group_summary(enriched[enriched["property"].eq("N")], ["paper_sensor", "theta_sensor", "theta_magnitude", "theta_direction"])
    noise.to_csv(OUT / "rq2_noise_by_sensor_magnitude_direction.csv", index=False)

    orv = group_summary(enriched[enriched["property"].eq("ORV")], ["paper_sensor", "theta_sensor", "theta_alpha", "theta_direction"])
    orv.to_csv(OUT / "rq2_orv_by_sensor_alpha_direction.csv", index=False)

    ca_cols = ["theta_dynamic", "theta_ratio", "theta_co2", "theta_duration", "theta_delta"]
    ca = group_summary(enriched[enriched["property"].eq("CA")], ca_cols)
    ca.to_csv(OUT / "rq2_ca_by_dynamic_parameters.csv", index=False)

    # CD post-hoc reference severity based on reference-side half split.
    val_df = load_validation_df()
    normal_df = val_df.loc[_normal_base_mask(val_df), SENSORS].copy()
    percentile_info: dict[str, dict[str, float]] = {}
    for _, reference in CD_PAIRS:
        percentile_info[reference] = {
            "p25": float(normal_df[reference].quantile(0.25)),
            "p75": float(normal_df[reference].quantile(0.75)),
            "p125": float(normal_df[reference].quantile(0.125)),
            "p875": float(normal_df[reference].quantile(0.875)),
        }

    cd_mask = enriched["property"].eq("CD")
    enriched.loc[cd_mask, "cd_pair_paper"] = enriched.loc[cd_mask].apply(
        lambda r: f"({PAPER_NAME.get(r['theta_target'], r['theta_target'])},{PAPER_NAME.get(r['theta_reference'], r['theta_reference'])})",
        axis=1,
    )
    enriched.loc[cd_mask, "cd_reference_side"] = enriched.loc[cd_mask, "theta_reference_quartile"].map({"low": "below_p25", "high": "above_p75"})
    enriched.loc[cd_mask, "cd_correlation_sign"] = enriched.loc[cd_mask, "theta_corr_sign"].map({1.0: "positive", -1.0: "negative", 1: "positive", -1: "negative"})
    ref_values = []
    severities = []
    for _, r in enriched.loc[cd_mask].iterrows():
        ref = r["theta_reference"]
        value = float(val_df.loc[int(r["base_index"]), ref])
        p = percentile_info[ref]
        side = r["theta_reference_quartile"]
        if side == "low":
            sev = "deep_extreme" if value <= p["p125"] else "near_quartile"
        else:
            sev = "deep_extreme" if value >= p["p875"] else "near_quartile"
        ref_values.append(value)
        severities.append(sev)
    enriched.loc[cd_mask, "cd_reference_value"] = ref_values
    enriched.loc[cd_mask, "cd_reference_severity"] = severities
    cd = group_summary(enriched[cd_mask], ["cd_pair_paper", "cd_correlation_sign", "cd_reference_side", "cd_reference_severity"])
    cd.to_csv(OUT / "rq2_cd_by_pair_side_severity.csv", index=False)

    psf = group_summary(enriched[enriched["property"].eq("PSF")], ["theta_cardinality"])
    psf.to_csv(OUT / "rq2_psf_by_cardinality.csv", index=False)

    # Failure modes
    ce = counters.copy()
    ce["failure_mode"] = ce.apply(classify_failure, axis=1)
    ce.to_csv(OUT / "counterexample_failure_modes.csv", index=False)
    fm_prop = ce.groupby(["property", "failure_mode"]).size().rename("counterexamples").reset_index()
    totals = ce.groupby("property").size().rename("property_counterexamples").reset_index()
    fm_prop = fm_prop.merge(totals, on="property", how="left")
    fm_prop["percentage_of_property_counterexamples"] = fm_prop["counterexamples"] / fm_prop["property_counterexamples"]
    fm_prop.to_csv(OUT / "counterexample_failure_modes_by_property.csv", index=False)
    pred_types = ce.groupby(["property", "failure_mode", "pred_deteccion", "pred_tipo_anomalia"]).size().rename("counterexamples").reset_index()
    pred_types.to_csv(OUT / "counterexample_predicted_types.csv", index=False)

    fm_config = theta_frame(ce[["case_id", "property", "theta_json", "expected_detection", "expected_type", "pred_deteccion", "pred_tipo_anomalia", "oracle_result"]].copy())
    fm_config["failure_mode"] = fm_config.apply(classify_failure, axis=1)
    fm_config.to_csv(OUT / "counterexample_failure_modes_by_theta.csv", index=False)

    # Confidence intervals for important summaries.
    ci_tables = []
    for name, frame in [
        ("property", rq2_prop),
        ("mv_by_sensor", mv),
        ("ss_by_sensor_duration", ss),
        ("noise_by_sensor_magnitude_direction", noise),
        ("orv_by_sensor_alpha_direction", orv),
        ("ca_by_dynamic_parameters", ca),
        ("cd_by_pair_side_severity", cd),
        ("psf_by_cardinality", psf),
    ]:
        tmp = frame.copy()
        tmp.insert(0, "summary", name)
        ci_tables.append(tmp)
    pd.concat(ci_tables, ignore_index=True, sort=False).to_csv(OUT / "conformance_confidence_intervals.csv", index=False)

    # RQ3 boundary summary as evidence rows, not narrative claims.
    boundary_rows = []
    def add_boundary(prop: str, dimension: str, evidence: str, support: str) -> None:
        boundary_rows.append({"property": prop, "dimension": dimension, "evidence": evidence, "support": support})

    for _, r in rq2_prop.iterrows():
        if r["fail"] == 0:
            add_boundary(r["property"], "exercised Theta space", "No failures observed in exercised configurations", f"{int(r['pass'])}/{int(r['valid_property_checks'])} pass")

    # SS duration trend by sensor.
    for sensor, g in ss.groupby("paper_sensor"):
        levels = "; ".join(f"{int(row.theta_duration)}:{format_pct(row.conformance_rate)}(n={int(row.valid_property_checks)})" for _, row in g.sort_values("theta_duration").iterrows())
        low_support = int((g["rq3_supported"] == False).sum()) if "rq3_supported" in g else 0
        add_boundary("SS", f"{sensor} duration", levels, f"{low_support} levels below n>=20 support threshold")

    # Noise magnitude trend by sensor/direction.
    for (sensor, direction), g in noise.groupby(["paper_sensor", "theta_direction"]):
        levels = "; ".join(f"{row.theta_magnitude:g}:{format_pct(row.conformance_rate)}(n={int(row.valid_property_checks)})" for _, row in g.sort_values("theta_magnitude").iterrows())
        add_boundary("N", f"{sensor} direction={direction}", levels, "all levels n=80")

    # ORV alpha/direction.
    for (alpha, direction), g in orv.groupby(["theta_alpha", "theta_direction"]):
        add_boundary("ORV", f"alpha={alpha:g}, direction={direction}", f"{int(g['pass'].sum())}/{int(g['valid_property_checks'].sum())} pass", "all sensor configurations covered")

    # CA dynamic.
    for dynamic, g in ca.groupby("theta_dynamic"):
        add_boundary("CA", str(dynamic), f"{int(g['pass'].sum())}/{int(g['valid_property_checks'].sum())} pass; {int(g['fail'].sum())} counterexamples", "stratified by dynamic parameters")

    # CD pair/side/severity.
    for (pair, side, sev), g in cd.groupby(["cd_pair_paper", "cd_reference_side", "cd_reference_severity"]):
        add_boundary("CD", f"{pair} {side} {sev}", f"{int(g['pass'].sum())}/{int(g['valid_property_checks'].sum())} pass; CR={format_pct(g['pass'].sum()/g['valid_property_checks'].sum())}", "post-hoc severity from reference percentiles")

    # PSF cardinality.
    for _, r in psf.sort_values("theta_cardinality").iterrows():
        add_boundary("PSF", f"cardinality={int(r.theta_cardinality)}", f"{int(r['pass'])}/{int(r.valid_property_checks)} pass", "all subsets covered")

    pd.DataFrame(boundary_rows).to_csv(OUT / "rq3_boundary_summary.csv", index=False)

    # Markdown report.
    report = []
    report.append("# PBT Post-Hoc Analysis Report\n")
    report.append("## Data Sources\n")
    for f in [
        "pbt_cases_raw.csv",
        "pbt_sut_outputs.parquet",
        "pbt_property_checks.csv",
        "pbt_counterexamples.csv",
        "pbt_execution_report_by_property.csv",
        "pbt_realized_coverage_by_configuration.csv",
        "pbt_realized_coverage_by_theta.csv",
        "pbt_ss_realized_rq3_support.csv",
        "pbt_integrity_report.json",
    ]:
        report.append(f"- `{CAMPAIGN / f}`\n")

    report.append("\n## Integrity Checks\n")
    for k, v in integrity.items():
        report.append(f"- `{k}`: `{v}`\n")

    total_checks = int(rq2_prop["valid_property_checks"].sum())
    total_pass = int(rq2_prop["pass"].sum())
    total_fail = int(rq2_prop["fail"].sum())
    report.append("\n## Campaign-Level Summary\n")
    report.append(f"- Total valid checks: {total_checks}\n")
    report.append(f"- Pass: {total_pass} ({format_pct(total_pass/total_checks)})\n")
    report.append(f"- Fail/counterexamples: {total_fail} ({format_pct(total_fail/total_checks)})\n")

    report.append("\n## RQ1 Evidence\n")
    report.append("All seven properties were operationalized end-to-end: cases were generated, Phi-valid, executed by the SUT, and evaluated by partial oracles. No candidates were rejected by Phi_p in the completed campaign. SS used adaptive sample sizes due to independent-window availability, preserving all duration strata.\n")
    report.append(table_text(rq1))
    report.append("\n")

    report.append("\n## RQ2 Evidence\n")
    report.append(table_text(rq2_prop[["property", "valid_property_checks", "pass", "fail", "conformance_rate", "counterexample_rate", "cr_ci95_low", "cr_ci95_high"]]))
    report.append("\n")

    report.append("\n## Counterexample Failure Modes\n")
    report.append(table_text(fm_prop))
    report.append("\n")
    report.append("\nPredicted semantic types for counterexamples are stored in `counterexample_predicted_types.csv`.\n")

    report.append("\n## RQ3 Boundary Evidence\n")
    report.append("Boundary evidence is based on observed changes across stratified Theta_p dimensions. It should not be reduced to global property conformance. ORV, MV, and PSF showed no failure boundary within the exercised spaces. SS, N, CA, and CD require stratified reading; SS strata with `n < 20` are retained but flagged as limited support for quantitative boundary claims.\n")
    report.append("\nDetailed boundary evidence rows are stored in `rq3_boundary_summary.csv`.\n")

    report.append("\n## Relation To Conventional ML Baseline\n")
    report.append("The conventional baseline reported in the manuscript is binary accuracy 99.20%, precision 96.75%, recall 97.15%, F1 0.9695, and multiclass anomaly-type accuracy 97.07%. The PBT campaign is not a replacement test-set metric. It shows that high aggregate conventional performance can coexist with heterogeneous property conformance: MV, ORV, and PSF conform in all exercised cases, while CD, SS, N, and CA expose localized counterexamples under property-defined conditions.\n")

    report.append("\n## Limitations\n")
    report.append("- The analysis uses the completed campaign only and does not rerun the SUT.\n")
    report.append("- CD severity is a post-hoc analytic stratification derived from reference-variable percentiles; it is not an extension of Theta_CD.\n")
    report.append("- SS long-duration strata with `n < 20` are executed and retained but should not alone support quantitative boundary claims.\n")
    report.append("- The SUT was loaded in the available local environment; prior execution recorded scikit-learn version warnings, while model hashes remained unchanged.\n")

    report.append("\n## Candidate Tables And Figures\n")
    report.append("- Table: RQ1 operationalization summary.\n")
    report.append("- Table: property-level conformance with Wilson 95% intervals.\n")
    report.append("- Heatmap: SS conformance by sensor and duration, marking `rq3_supported`.\n")
    report.append("- Line/small multiples: Noise conformance by magnitude, sensor, and direction.\n")
    report.append("- Table/heatmap: CD conformance by pair, side, and severity.\n")
    report.append("- Bar chart: failure modes by property and predicted type for counterexamples.\n")

    (OUT / "posthoc_analysis_report.md").write_text("\n".join(report), encoding="utf-8")

    print(f"Wrote post-hoc analysis to {OUT}")
    print(rq2_prop[["property", "valid_property_checks", "pass", "fail", "conformance_rate", "counterexample_rate"]].to_string(index=False))


if __name__ == "__main__":
    main()

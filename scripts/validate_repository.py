"""Validate the distributable PBT replication package.

This check does not require the original greenhouse dataset. It verifies the
distributed configuration, aggregate campaign artifacts, post-hoc summaries,
and the absence of intentionally excluded case-level files.
"""

from __future__ import annotations

import csv
import importlib.util
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src" / "pbt_campaign"
CAMPAIGN = ROOT / "results" / "pbt_campaign" / "campaign_20260928_150110"
POSTHOC = CAMPAIGN / "posthoc_analysis"


EXPECTED_BY_PROPERTY = {
    "CA": {"planned_checks": 1500, "valid_property_checks": 1500, "pass": 1490, "fail": 10, "counterexamples": 10},
    "CD": {"planned_checks": 1600, "valid_property_checks": 1600, "pass": 326, "fail": 1274, "counterexamples": 1274},
    "MV": {"planned_checks": 4500, "valid_property_checks": 4500, "pass": 4500, "fail": 0, "counterexamples": 0},
    "N": {"planned_checks": 6000, "valid_property_checks": 6000, "pass": 5470, "fail": 530, "counterexamples": 530},
    "ORV": {"planned_checks": 7200, "valid_property_checks": 7200, "pass": 7200, "fail": 0, "counterexamples": 0},
    "PSF": {"planned_checks": 3810, "valid_property_checks": 3810, "pass": 3810, "fail": 0, "counterexamples": 0},
    "SS": {"planned_checks": 2157, "valid_property_checks": 2157, "pass": 1435, "fail": 722, "counterexamples": 722},
}

EXPECTED_EXECUTED_TOTAL = 26767
EXPECTED_PASS_TOTAL = 24231
EXPECTED_FAIL_TOTAL = 2536

DISALLOWED_PUBLIC_FILES = [
    CAMPAIGN / "pbt_cases_raw.csv",
    CAMPAIGN / "pbt_cases_raw.parquet",
    CAMPAIGN / "pbt_property_checks.csv",
    CAMPAIGN / "pbt_counterexamples.csv",
    CAMPAIGN / "pbt_sut_outputs.parquet",
    CAMPAIGN / "pbt_execution_errors.csv",
    CAMPAIGN / "pbt_phi_rejections.csv",
]


def fail(message: str) -> None:
    raise SystemExit(f"ERROR: {message}")


def read_csv_dicts(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        fail(f"missing required file: {path.relative_to(ROOT)}")
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def load_pbt_config():
    path = SRC / "pbt_config.py"
    spec = importlib.util.spec_from_file_location("pbt_config_for_validation", path)
    if spec is None or spec.loader is None:
        fail(f"cannot load {path.relative_to(ROOT)}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def validate_configuration() -> None:
    cfg = load_pbt_config()
    expected_raw = cfg.expected_checks()
    if isinstance(expected_raw, dict):
        expected = expected_raw
    else:
        expected = {item.property_name: item.checks for item in expected_raw}
    planned_reference = {
        "MV": 4500,
        "SS": 4000,
        "N": 6000,
        "ORV": 7200,
        "CA": 1500,
        "CD": 1600,
        "PSF": 3810,
    }
    if expected != planned_reference:
        fail(f"pbt_config.expected_checks()={expected}, expected {planned_reference}")
    psf_counts = {k: len(v) for k, v in cfg.psf_subsets_by_cardinality().items()}
    if psf_counts != {4: 126, 5: 126, 6: 84, 7: 36, 8: 9}:
        fail(f"unexpected PSF subset counts: {psf_counts}")
    if cfg.RANDOM_SEED != 20261001:
        fail(f"unexpected random seed: {cfg.RANDOM_SEED}")


def validate_property_report() -> None:
    rows = read_csv_dicts(CAMPAIGN / "pbt_execution_report_by_property.csv")
    observed = {row["property"]: row for row in rows}
    if set(observed) != set(EXPECTED_BY_PROPERTY):
        fail(f"unexpected property set in execution report: {sorted(observed)}")

    total_valid = total_pass = total_fail = 0
    for prop, expected in EXPECTED_BY_PROPERTY.items():
        row = observed[prop]
        for key, value in expected.items():
            actual = int(row[key])
            if actual != value:
                fail(f"{prop}.{key}={actual}, expected {value}")
        if int(row["pass"]) + int(row["fail"]) != int(row["valid_property_checks"]):
            fail(f"{prop} violates pass + fail = valid_property_checks")
        total_valid += int(row["valid_property_checks"])
        total_pass += int(row["pass"])
        total_fail += int(row["fail"])

    if (total_valid, total_pass, total_fail) != (EXPECTED_EXECUTED_TOTAL, EXPECTED_PASS_TOTAL, EXPECTED_FAIL_TOTAL):
        fail(f"unexpected campaign totals: {(total_valid, total_pass, total_fail)}")


def validate_integrity_report() -> None:
    path = CAMPAIGN / "pbt_integrity_report.json"
    if not path.exists():
        fail(f"missing required file: {path.relative_to(ROOT)}")
    integrity = json.loads(path.read_text(encoding="utf-8"))
    expected_flags = {
        "all_cases_have_theta": True,
        "every_fail_in_counterexamples": True,
        "model_artifacts_unchanged": True,
        "no_pass_in_counterexamples": True,
        "pass_fail_equals_valid": True,
        "pbt_cases_written_only_to_results": True,
    }
    for key, value in expected_flags.items():
        if integrity.get(key) is not value:
            fail(f"integrity flag {key}={integrity.get(key)}, expected {value}")
    expected_counts = {
        "cases_generated": EXPECTED_EXECUTED_TOTAL,
        "property_checks": EXPECTED_EXECUTED_TOTAL,
        "sut_outputs": EXPECTED_EXECUTED_TOTAL,
        "counterexamples": EXPECTED_FAIL_TOTAL,
        "execution_errors": 0,
        "phi_rejection_rows": 0,
        "random_seed": 20261001,
    }
    for key, value in expected_counts.items():
        if int(integrity.get(key, -1)) != value:
            fail(f"integrity count {key}={integrity.get(key)}, expected {value}")


def validate_boundary_details() -> None:
    checks = [
        ("rq3_ss_boundary_detail.csv", 40, 2157, 1435, 722),
        ("rq3_n_boundary_detail.csv", 75, 6000, 5470, 530),
        ("rq3_cd_boundary_detail.csv", 16, 1600, 326, 1274),
    ]
    for filename, rows_expected, checks_expected, passes_expected, failures_expected in checks:
        rows = read_csv_dicts(POSTHOC / filename)
        checks_sum = sum(int(row["checks"]) for row in rows)
        passes_sum = sum(int(row["passes"]) for row in rows)
        failures_sum = sum(int(row["counterexamples"]) for row in rows)
        if (len(rows), checks_sum, passes_sum, failures_sum) != (
            rows_expected,
            checks_expected,
            passes_expected,
            failures_expected,
        ):
            fail(
                f"{filename} totals={(len(rows), checks_sum, passes_sum, failures_sum)}, "
                f"expected={(rows_expected, checks_expected, passes_expected, failures_expected)}"
            )
        for idx, row in enumerate(rows, 1):
            if int(row["checks"]) != int(row["passes"]) + int(row["counterexamples"]):
                fail(f"{filename} row {idx} violates checks = passes + counterexamples")


def validate_public_file_policy() -> None:
    present = [path.relative_to(ROOT) for path in DISALLOWED_PUBLIC_FILES if path.exists()]
    if present:
        fail("case-level/private campaign files are present in the public package: " + ", ".join(map(str, present)))
    data_dir = ROOT / "data" / "interim"
    if data_dir.exists() and any(data_dir.iterdir()):
        fail("data/interim is not empty; the public package must not include the original dataset")


def main() -> None:
    validate_configuration()
    validate_property_report()
    validate_integrity_report()
    validate_boundary_details()
    validate_public_file_policy()
    print("Repository validation OK")
    print(f"Valid property checks: {EXPECTED_EXECUTED_TOTAL}")
    print(f"Pass: {EXPECTED_PASS_TOTAL}")
    print(f"Counterexamples: {EXPECTED_FAIL_TOTAL}")


if __name__ == "__main__":
    main()

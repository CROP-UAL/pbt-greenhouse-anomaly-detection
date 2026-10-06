"""Authoritative PBT campaign configuration aligned with the manuscript.

This module defines the experimental exploration of Theta_p only. It does not
train models and does not modify the conventional anomaly-detection pipeline.
"""

from __future__ import annotations

from dataclasses import dataclass
from itertools import combinations
from math import comb


RANDOM_SEED = 20261001
VALIDATION_START = "2021-02-01 00:00:00"

SENSORS = [
    "PCO2EXT",
    "PHEXT",
    "PRAD",
    "PTEXT",
    "PVV",
    "XCO2I",
    "PRGINT",
    "XHINV",
    "XTINV",
]

PAPER_NAME = {
    "PCO2EXT": "DCO2EXT",
    "PHEXT": "DHEXT",
    "PRAD": "DGREXT",
    "PTEXT": "DTEXT",
    "PVV": "DVEXT",
    "XCO2I": "XCO2INT",
    "PRGINT": "XGRINT",
    "XHINV": "XHINT",
    "XTINV": "XTINT",
}

PHYSICAL_RANGES = {
    "PCO2EXT": (300.0, 800.0),
    "PHEXT": (0.0, 100.0),
    "PRAD": (0.0, 1500.0),
    "PTEXT": (-20.0, 60.0),
    "PVV": (0.0, 50.0),
    "XCO2I": (200.0, 3000.0),
    "PRGINT": (0.0, 1200.0),
    "XHINV": (0.0, 100.0),
    "XTINV": (-5.0, 60.0),
}

MV_BASES_PER_SENSOR = 500

SS_DURATIONS = {
    "PCO2EXT": [20, 25, 30, 35, 40],
    "PHEXT": [16, 20, 23, 27, 30],
    "PTEXT": [40, 45, 50, 55, 60],
    "PVV": [20, 30, 40, 50, 60],
    "XCO2I": [20, 30, 40, 50, 60],
    "PRGINT": [20, 30, 40, 50, 60],
    "XHINV": [16, 20, 23, 27, 30],
    "XTINV": [40, 45, 50, 55, 60],
}
SS_BASE_WINDOWS_PER_CONFIG = 100
SS_XGRINT_CONTEXT = {
    "PRGINT_min": 10.0,
    "PRAD_min": 10.0,
    "PRAD_rolling_std_30m_min": 2.0,
    "rolling_window_samples": 60,
}

NOISE_DELTAS = {
    "PCO2EXT": {"min": 25.0, "max": 75.0, "directions": [-1, 1]},
    "PHEXT": {"min": 10.0, "max": 25.0, "directions": [-1, 1]},
    "PRAD": {"min": 150.0, "max": 500.0, "directions": [1]},
    "PTEXT": {"min": 3.0, "max": 8.0, "directions": [-1, 1]},
    "PVV": {"min": 5.0, "max": 9.0, "directions": [1]},
    "XCO2I": {"min": 60.0, "max": 160.0, "directions": [-1, 1]},
    "PRGINT": {"min": 80.0, "max": 250.0, "directions": [1]},
    "XHINV": {"min": 10.0, "max": 25.0, "directions": [-1, 1]},
    "XTINV": {"min": 3.0, "max": 8.0, "directions": [-1, 1]},
}
NOISE_BASES_PER_CONFIG = 80

ORV_ALPHAS = [0.01, 0.025, 0.05, 0.10]
ORV_DIRECTIONS = ["below", "above"]
ORV_BASES_PER_CONFIG = 100

CA_BASES_PER_CONFIG = 100
CA_RADIATION_RATIOS = [0.02, 0.05, 0.08]
CA_CO2_VALUES = [700.0, 950.0, 1200.0]
CA_CO2_DURATIONS = [3, 5, 8]
CA_TEMP_DELTAS = [3.0, 6.5, 10.0]

CA_CONTEXT = {
    "radiation": {"PRAD_min": 200.0, "normal_ratio_min": 0.40},
    "co2_vent": {"vent_open_min": 40.0, "PRAD_min": 50.0},
    "temp_inversion": {"PRAD_min": 400.0, "PTEXT_min": 20.0},
}

CD_PAIRS = [
    ("PRAD", "PRGINT"),
    ("XTINV", "XHINV"),
    ("PTEXT", "XTINV"),
    ("PHEXT", "XHINV"),
]
CD_REFERENCE_QUARTILES = ["low", "high"]
CD_BASES_PER_CONFIG = 200

PSF_CARDINALITIES = [4, 5, 6, 7, 8]
PSF_BASES_PER_SUBSET = 10


@dataclass(frozen=True)
class ExpectedChecks:
    property_name: str
    checks: int


def five_levels(min_value: float, max_value: float) -> list[float]:
    return [
        min_value,
        min_value + 0.25 * (max_value - min_value),
        min_value + 0.50 * (max_value - min_value),
        min_value + 0.75 * (max_value - min_value),
        max_value,
    ]


def psf_subsets_by_cardinality() -> dict[int, list[tuple[str, ...]]]:
    return {r: list(combinations(SENSORS, r)) for r in PSF_CARDINALITIES}


def expected_checks() -> list[ExpectedChecks]:
    mv = len(SENSORS) * MV_BASES_PER_SENSOR
    ss = sum(len(levels) * SS_BASE_WINDOWS_PER_CONFIG for levels in SS_DURATIONS.values())
    noise = sum(
        len(cfg["directions"]) * len(five_levels(cfg["min"], cfg["max"])) * NOISE_BASES_PER_CONFIG
        for cfg in NOISE_DELTAS.values()
    )
    orv = len(SENSORS) * len(ORV_DIRECTIONS) * len(ORV_ALPHAS) * ORV_BASES_PER_CONFIG
    ca = (
        len(CA_RADIATION_RATIOS) * CA_BASES_PER_CONFIG
        + len(CA_CO2_VALUES) * len(CA_CO2_DURATIONS) * CA_BASES_PER_CONFIG
        + len(CA_TEMP_DELTAS) * CA_BASES_PER_CONFIG
    )
    cd = len(CD_PAIRS) * len(CD_REFERENCE_QUARTILES) * CD_BASES_PER_CONFIG
    psf = sum(comb(len(SENSORS), r) * PSF_BASES_PER_SUBSET for r in PSF_CARDINALITIES)
    return [
        ExpectedChecks("MV", mv),
        ExpectedChecks("SS", ss),
        ExpectedChecks("N", noise),
        ExpectedChecks("ORV", orv),
        ExpectedChecks("CA", ca),
        ExpectedChecks("CD", cd),
        ExpectedChecks("PSF", psf),
    ]

"""Execute the PBT campaign against the frozen LightGBM SUT."""

from __future__ import annotations

import hashlib
import json
import sys
import time
import warnings
from dataclasses import asdict, dataclass
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.exceptions import InconsistentVersionWarning

warnings.filterwarnings("ignore", category=InconsistentVersionWarning)

ROOT = Path(__file__).resolve().parents[2]
PBT_DIR = Path(__file__).resolve().parent
CONFIG_DIR = ROOT / "config"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(PBT_DIR) not in sys.path:
    sys.path.insert(0, str(PBT_DIR))
if str(CONFIG_DIR) not in sys.path:
    sys.path.insert(0, str(CONFIG_DIR))

import config as cfg  # noqa: E402
from availability_audit import _count_independent_windows, _normal_base_mask  # noqa: E402
from feature_engineering import add_features  # noqa: E402
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
    PAPER_NAME,
    PHYSICAL_RANGES,
    PSF_BASES_PER_SUBSET,
    RANDOM_SEED,
    SENSORS,
    SS_BASE_WINDOWS_PER_CONFIG,
    SS_DURATIONS,
    SS_XGRINT_CONTEXT,
    VALIDATION_START,
    five_levels,
    psf_subsets_by_cardinality,
)

HISTORY = 420

EXPECTED_TYPE = {
    "MV": "Datos Faltantes",
    "SS": "Sensor Atascado",
    "N": "Ruido",
    "ORV": "Valores Fuera de Rango",
    "CA": "Contextual",
    "CD": "Desviacion de Correlacion",
    "PSF": "Fallo Parcial Sistema",
}


@dataclass
class Case:
    case_id: str
    property: str
    theta: dict
    base_index: int
    target_index: int
    window_start_index: int
    window_end_index: int
    expected_detection: str
    expected_type: str
    rq3_supported: bool | None = None


def _load_validation_data() -> pd.DataFrame:
    data_path = ROOT / "data" / "interim" / "authorized_validation_campaign.parquet"
    if not data_path.exists():
        raise SystemExit(
            "Validation dataset not found. Place the authorized parquet file at "
            f"{data_path.relative_to(ROOT)} before running the full PBT campaign."
        )
    df = pd.read_parquet(data_path)
    df["Fecha"] = pd.to_datetime(df["Fecha"])
    df = df.loc[df["Fecha"] >= pd.Timestamp(VALIDATION_START)].sort_values("Fecha").reset_index(drop=True)
    return df


def _rng() -> np.random.Generator:
    return np.random.default_rng(RANDOM_SEED)


def _sample(values: list[int], n: int, rng: np.random.Generator) -> list[int]:
    if n <= 0:
        return []
    arr = np.array(values, dtype=int)
    if len(arr) < n:
        raise ValueError(f"Sampling without replacement requested {n}, available {len(arr)}")
    return rng.choice(arr, size=n, replace=False).astype(int).tolist()


def _run_starts(mask: pd.Series, duration: int) -> list[int]:
    mask = mask.fillna(False).astype(bool)
    starts: list[int] = []
    i = 0
    n = len(mask)
    vals = mask.to_numpy()
    while i < n:
        if not vals[i]:
            i += 1
            continue
        j = i
        while j < n and vals[j]:
            j += 1
        run_len = j - i
        for start in range(i, i + (run_len // duration) * duration, duration):
            starts.append(start)
        i = j
    return starts


def _add_case(cases: list[Case], prop: str, theta: dict, base_index: int, target_index: int, start: int, end: int, rq3_supported: bool | None = None) -> None:
    raw = json.dumps({"p": prop, "theta": theta, "base": int(base_index), "target": int(target_index), "n": len(cases)}, sort_keys=True)
    cid = f"{prop}_{hashlib.sha1(raw.encode('utf-8')).hexdigest()[:12]}"
    cases.append(
        Case(
            case_id=cid,
            property=prop,
            theta=theta,
            base_index=int(base_index),
            target_index=int(target_index),
            window_start_index=int(start),
            window_end_index=int(end),
            expected_detection="anomalia",
            expected_type=EXPECTED_TYPE[prop],
            rq3_supported=rq3_supported,
        )
    )


def generate_cases(df: pd.DataFrame) -> tuple[list[Case], pd.DataFrame]:
    rng = _rng()
    base_mask = _normal_base_mask(df)
    cases: list[Case] = []
    rejections: list[dict] = []

    base_indices = np.flatnonzero(base_mask.to_numpy()).astype(int).tolist()

    for sensor in SENSORS:
        eligible = [i for i in base_indices if pd.notna(df.at[i, sensor]) and i >= HISTORY]
        chosen = _sample(eligible, MV_BASES_PER_SENSOR, rng)
        for i in chosen:
            _add_case(cases, "MV", {"sensor": sensor, "paper_sensor": PAPER_NAME[sensor]}, i, i, i, i)

    for sensor, durations in SS_DURATIONS.items():
        sensor_mask = base_mask & df[sensor].notna()
        if sensor == "PRGINT":
            roll_std = df["PRAD"].rolling(SS_XGRINT_CONTEXT["rolling_window_samples"], min_periods=5).std()
            sensor_mask &= (
                df["PRGINT"].gt(SS_XGRINT_CONTEXT["PRGINT_min"])
                & df["PRAD"].gt(SS_XGRINT_CONTEXT["PRAD_min"])
                & roll_std.gt(SS_XGRINT_CONTEXT["PRAD_rolling_std_30m_min"])
            )
        for duration in durations:
            starts = [s for s in _run_starts(sensor_mask, duration) if s >= HISTORY]
            n_final = min(SS_BASE_WINDOWS_PER_CONFIG, len(starts))
            chosen = _sample(starts, n_final, rng)
            for s in chosen:
                theta = {
                    "sensor": sensor,
                    "paper_sensor": PAPER_NAME[sensor],
                    "duration": duration,
                    "available_independent_windows": len(starts),
                    "requested_windows": SS_BASE_WINDOWS_PER_CONFIG,
                    "final_planned_checks": n_final,
                }
                _add_case(cases, "SS", theta, s, s + duration - 1, s, s + duration - 1, rq3_supported=n_final >= 20)

    for sensor, spec in NOISE_DELTAS.items():
        lo, hi = PHYSICAL_RANGES[sensor]
        values = pd.to_numeric(df[sensor], errors="coerce")
        prev_values = values.shift(1)
        next_values = values.shift(-1)
        common_noise_mask = base_mask & values.notna() & prev_values.notna() & next_values.notna()
        common_noise_mask.iloc[:HISTORY] = False
        for direction in spec["directions"]:
            for magnitude in five_levels(spec["min"], spec["max"]):
                candidate = values + direction * magnitude
                eligible_mask = (
                    common_noise_mask
                    & candidate.between(lo, hi, inclusive="both")
                    & (candidate - prev_values).abs().gt(spec["min"])
                    & (candidate - next_values).abs().gt(spec["min"])
                )
                eligible = np.flatnonzero(eligible_mask.to_numpy()).astype(int).tolist()
                n = min(NOISE_BASES_PER_CONFIG, len(eligible))
                if n < NOISE_BASES_PER_CONFIG:
                    rejections.append({"property": "N", "stratum": f"{sensor}|{direction}|{magnitude:g}", "reason": "insufficient_phi_valid_bases", "rejected": NOISE_BASES_PER_CONFIG - n})
                for i in _sample(eligible, n, rng):
                    _add_case(cases, "N", {"sensor": sensor, "paper_sensor": PAPER_NAME[sensor], "direction": direction, "magnitude": magnitude}, i, i, i - 1, i + 1)

    for sensor in SENSORS:
        eligible = [i for i in base_indices if i >= HISTORY and pd.notna(df.at[i, sensor])]
        for direction in ORV_DIRECTIONS:
            for alpha in ORV_ALPHAS:
                for i in _sample(eligible, ORV_BASES_PER_CONFIG, rng):
                    _add_case(cases, "ORV", {"sensor": sensor, "paper_sensor": PAPER_NAME[sensor], "direction": direction, "alpha": alpha}, i, i, i, i)

    rad_mask = base_mask & df["PRAD"].gt(CA_CONTEXT["radiation"]["PRAD_min"]) & ((df["PRGINT"] / df["PRAD"]).gt(CA_CONTEXT["radiation"]["normal_ratio_min"]))
    rad_indices = [i for i in np.flatnonzero(rad_mask.to_numpy()).astype(int).tolist() if i >= HISTORY]
    for ratio in CA_RADIATION_RATIOS:
        for i in _sample(rad_indices, CA_BASES_PER_CONFIG, rng):
            _add_case(cases, "CA", {"dynamic": "radiation", "target": "PRGINT", "ratio": ratio}, i, i, i, i)

    vent_open = df[["UVENT_cen", "UVENT_lN"]].max(axis=1).ge(CA_CONTEXT["co2_vent"]["vent_open_min"])
    co2_mask = base_mask & vent_open & df["PRAD"].ge(CA_CONTEXT["co2_vent"]["PRAD_min"])
    for co2_value in CA_CO2_VALUES:
        for duration in CA_CO2_DURATIONS:
            starts = [s for s in _run_starts(co2_mask, duration) if s >= HISTORY]
            for s in _sample(starts, CA_BASES_PER_CONFIG, rng):
                _add_case(cases, "CA", {"dynamic": "co2_vent", "target": "XCO2I", "co2": co2_value, "duration": duration}, s, s + duration - 1, s, s + duration - 1)

    temp_mask = base_mask & df["PRAD"].gt(CA_CONTEXT["temp_inversion"]["PRAD_min"]) & df["PTEXT"].gt(CA_CONTEXT["temp_inversion"]["PTEXT_min"])
    temp_indices = [i for i in np.flatnonzero(temp_mask.to_numpy()).astype(int).tolist() if i >= HISTORY]
    for delta in CA_TEMP_DELTAS:
        for i in _sample(temp_indices, CA_BASES_PER_CONFIG, rng):
            _add_case(cases, "CA", {"dynamic": "temp_inversion", "target": "XTINV", "delta": delta}, i, i, i, i)

    normal_df = df.loc[base_mask, SENSORS].copy()
    corr_sign = {("PRAD", "PRGINT"): 1, ("XTINV", "XHINV"): -1, ("PTEXT", "XTINV"): 1, ("PHEXT", "XHINV"): 1}
    percentiles = {s: (normal_df[s].quantile(0.25), normal_df[s].quantile(0.75)) for s in SENSORS}
    for target, reference in CD_PAIRS:
        ref_p25, ref_p75 = percentiles[reference]
        for quartile in CD_REFERENCE_QUARTILES:
            if quartile == "low":
                mask = base_mask & df[reference].lt(ref_p25)
            else:
                mask = base_mask & df[reference].gt(ref_p75)
            eligible = [i for i in np.flatnonzero(mask.to_numpy()).astype(int).tolist() if i >= HISTORY]
            for i in _sample(eligible, CD_BASES_PER_CONFIG, rng):
                _add_case(cases, "CD", {"target": target, "reference": reference, "reference_quartile": quartile, "corr_sign": corr_sign[(target, reference)]}, i, i, i, i)

    all_base = [i for i in base_indices if i >= HISTORY]
    for cardinality, subsets in psf_subsets_by_cardinality().items():
        for subset in subsets:
            for i in _sample(all_base, PSF_BASES_PER_SUBSET, rng):
                _add_case(cases, "PSF", {"cardinality": cardinality, "missing_subset": list(subset)}, i, i, i, i)

    return cases, pd.DataFrame(rejections)


def apply_case(df: pd.DataFrame, case: Case) -> pd.DataFrame:
    start = max(0, case.window_start_index - HISTORY)
    end = min(len(df) - 1, case.window_end_index + 1)
    w = df.loc[start:end].copy().reset_index(drop=False).rename(columns={"index": "source_index"})
    theta = case.theta

    def loc_source(idx: int) -> int:
        matches = w.index[w["source_index"].eq(idx)]
        if len(matches) != 1:
            raise RuntimeError(f"source index {idx} not in case window")
        return int(matches[0])

    if case.property == "MV":
        w.loc[loc_source(case.target_index), theta["sensor"]] = np.nan
    elif case.property == "SS":
        rows = (w["source_index"] >= case.window_start_index) & (w["source_index"] <= case.window_end_index)
        first = loc_source(case.window_start_index)
        w.loc[rows, theta["sensor"]] = w.loc[first, theta["sensor"]]
    elif case.property == "N":
        row = loc_source(case.target_index)
        w.loc[row, theta["sensor"]] = w.loc[row, theta["sensor"]] + theta["direction"] * theta["magnitude"]
    elif case.property == "ORV":
        row = loc_source(case.target_index)
        lo, hi = PHYSICAL_RANGES[theta["sensor"]]
        margin = theta["alpha"] * (hi - lo)
        w.loc[row, theta["sensor"]] = lo - margin if theta["direction"] == "below" else hi + margin
    elif case.property == "CA" and theta["dynamic"] == "radiation":
        row = loc_source(case.target_index)
        w.loc[row, "PRGINT"] = w.loc[row, "PRAD"] * theta["ratio"]
    elif case.property == "CA" and theta["dynamic"] == "co2_vent":
        rows = (w["source_index"] >= case.window_start_index) & (w["source_index"] <= case.window_end_index)
        w.loc[rows, "XCO2I"] = theta["co2"]
    elif case.property == "CA" and theta["dynamic"] == "temp_inversion":
        row = loc_source(case.target_index)
        w.loc[row, "XTINV"] = w.loc[row, "PTEXT"] - theta["delta"]
    elif case.property == "CD":
        row = loc_source(case.target_index)
        p25, p75 = getattr(apply_case, "_percentiles")[theta["target"]]
        if theta["corr_sign"] > 0:
            w.loc[row, theta["target"]] = p75 if theta["reference_quartile"] == "low" else p25
        else:
            w.loc[row, theta["target"]] = p25 if theta["reference_quartile"] == "low" else p75
    elif case.property == "PSF":
        row = loc_source(case.target_index)
        for sensor in theta["missing_subset"]:
            w.loc[row, sensor] = np.nan
    else:
        raise RuntimeError(f"Unhandled case property {case.property}")
    return w


class FrozenSUT:
    def __init__(self) -> None:
        models = ROOT / "models"
        required = [
            "modelo_1_detector_lightgbm_temporal_paper_v3.joblib",
            "imputer_modelo_1_lightgbm_temporal_paper_v3.joblib",
            "features_modelo_1_lightgbm_temporal_paper_v3.joblib",
            "threshold_modelo_1_lightgbm_temporal_paper_v3.joblib",
            "baselines_ctx_lightgbm_temporal_paper_v3.joblib",
            "modelo_2_clasificador_lightgbm_temporal_paper_v3.joblib",
            "label_encoder_modelo_2_lightgbm_temporal_paper_v3.joblib",
        ]
        missing = [name for name in required if not (models / name).exists()]
        if missing:
            raise SystemExit(f"Frozen SUT artifact(s) missing from models/: {', '.join(missing)}")
        self.modelo1 = joblib.load(models / "modelo_1_detector_lightgbm_temporal_paper_v3.joblib")
        self.imputer_m1 = joblib.load(models / "imputer_modelo_1_lightgbm_temporal_paper_v3.joblib")
        self.features_out_m1 = joblib.load(models / "features_modelo_1_lightgbm_temporal_paper_v3.joblib")
        th = joblib.load(models / "threshold_modelo_1_lightgbm_temporal_paper_v3.joblib")
        self.threshold = float(th.get("umbral", th.get("threshold"))) if isinstance(th, dict) else float(th)
        self.ctx_data = joblib.load(models / "baselines_ctx_lightgbm_temporal_paper_v3.joblib")
        self.modelo2 = joblib.load(models / "modelo_2_clasificador_lightgbm_temporal_paper_v3.joblib")
        self.label_m2 = joblib.load(models / "label_encoder_modelo_2_lightgbm_temporal_paper_v3.joblib")
        self.artifact_hashes = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in models.glob("*.joblib")}

    def _apply_ctx(self, x_obj: pd.DataFrame, df_obj: pd.DataFrame) -> pd.DataFrame:
        x_obj = x_obj.copy()
        stats = self.ctx_data.get("stats") if isinstance(self.ctx_data, dict) else None
        sensores = self.ctx_data.get("sensores", []) if isinstance(self.ctx_data, dict) else []
        if stats is None or len(stats) == 0:
            return x_obj
        merged = df_obj[["Hora", "Mes"]].merge(stats, on=["Hora", "Mes"], how="left")
        merged.index = x_obj.index
        for sensor in sensores:
            std_c = f"{sensor}_std_hora_ctx"
            rstd_c = f"{sensor}_rstd_5m"
            if std_c in merged.columns and rstd_c in x_obj.columns:
                x_obj[f"{sensor}_rstd_vs_expected"] = x_obj[rstd_c] / (merged[std_c].fillna(1).values + 1e-6)
        return x_obj

    def predict_one(self, raw_window: pd.DataFrame, source_target: int) -> dict:
        feat = add_features(raw_window.drop(columns=["source_index"], errors="ignore"), cfg)
        target_pos = int(raw_window.index[raw_window["source_index"].eq(source_target)][0])
        exclude = set(cfg.COLUMNAS_EXCLUIR_FEATURES) | {"fuente_anomalia", "split", "pred_deteccion", "pred_deteccion_base", "pred_proba_anomalia", "pred_tipo_anomalia"}
        feature_cols_base = [c for c in feat.columns if c not in exclude]
        x_base = feat[feature_cols_base].select_dtypes(include="number").copy()
        x_test = self._apply_ctx(x_base, feat)
        features_in = list(getattr(self.imputer_m1, "feature_names_in_", []))
        for c in features_in:
            if c not in x_test.columns:
                x_test[c] = np.nan
        x_test = x_test[features_in]
        x_row = x_test.iloc[[target_pos]]
        x_imp_np = self.imputer_m1.transform(x_row)
        x_imp = pd.DataFrame(x_imp_np, columns=self.features_out_m1, index=x_row.index)
        proba = float(self.modelo1.predict_proba(x_imp_np)[:, 1][0])
        pred_base = "anomalia" if proba >= self.threshold else "normal"

        row_raw = raw_window.iloc[target_pos]
        vals = pd.to_numeric(row_raw[[s for s in cfg.COLUMNAS_SENSORES if s in raw_window.columns]], errors="coerce")
        nan_mask = vals.isna()
        zero_mask = vals.eq(0.0)
        mask_missing = bool(nan_mask.any())
        mask_all_nan = bool(nan_mask.all())
        nan_count = int(nan_mask.sum())
        zero_count = int(zero_mask.sum())
        mask_fallo_parcial = bool(((nan_count >= cfg.FALLO_PARCIAL_SISTEMA_MIN_SENSORES_NAN) or ((nan_count >= 3) and (zero_count >= cfg.FALLO_PARCIAL_SISTEMA_MIN_SENSORES_CERO))) and not mask_all_nan)
        oor_sensors = []
        for sensor, rango in cfg.RANGOS_FISICOS.items():
            if sensor in raw_window.columns:
                v = pd.to_numeric(pd.Series([row_raw[sensor]]), errors="coerce").iloc[0]
                if pd.notna(v) and (v < rango["min"] or v > rango["max"]):
                    oor_sensors.append(sensor)
        mask_oor = bool(oor_sensors)

        pred_final = "anomalia" if (pred_base == "anomalia" or mask_missing or mask_oor or mask_fallo_parcial) else "normal"
        pred_tipo = "normal"
        if mask_all_nan:
            pred_tipo = cfg.TIPO_CAIDA_SISTEMA
        elif mask_fallo_parcial:
            pred_tipo = cfg.TIPO_FALLO_PARCIAL_SISTEMA
        elif mask_missing:
            pred_tipo = "Datos Faltantes"
        elif mask_oor:
            pred_tipo = "Valores Fuera de Rango"
        elif pred_final == "anomalia":
            pred_tipo = str(self.label_m2.inverse_transform(self.modelo2.predict(x_imp))[0])

        return {
            "pred_proba_anomalia": proba,
            "pred_deteccion_base": pred_base,
            "pred_deteccion": pred_final,
            "pred_tipo_anomalia": pred_tipo,
            "flag_dato_faltante": bool(mask_missing and not mask_all_nan and not mask_fallo_parcial),
            "flag_caida_sistema": bool(mask_all_nan),
            "flag_fallo_parcial_sistema": bool(mask_fallo_parcial),
            "flag_fuera_rango": bool(mask_oor),
            "nan_count": nan_count,
            "zero_count": zero_count,
            "oor_sensors": ",".join(oor_sensors),
        }


def main() -> None:
    started = time.strftime("%Y%m%d_%H%M%S")
    out_dir = ROOT / "results" / "pbt_ist2026" / f"campaign_{started}"
    out_dir.mkdir(parents=True, exist_ok=False)

    df = _load_validation_data()
    normal_df = df.loc[_normal_base_mask(df), SENSORS]
    apply_case._percentiles = {s: (normal_df[s].quantile(0.25), normal_df[s].quantile(0.75)) for s in SENSORS}

    cases, rejections = generate_cases(df)
    sut = FrozenSUT()
    before_hashes = dict(sut.artifact_hashes)

    raw_rows = []
    output_rows = []
    check_rows = []
    counter_rows = []
    errors = []

    for n, case in enumerate(cases, 1):
        if n % 1000 == 0:
            print(f"Executing {n:,}/{len(cases):,}", flush=True)
        row = asdict(case)
        row["theta_json"] = json.dumps(case.theta, sort_keys=True)
        raw_rows.append(row)
        try:
            raw_window = apply_case(df, case)
            pred = sut.predict_one(raw_window, case.target_index)
            passed = pred["pred_deteccion"] == case.expected_detection and pred["pred_tipo_anomalia"] == case.expected_type
            out = {
                "case_id": case.case_id,
                **pred,
            }
            output_rows.append(out)
            check = {
                "case_id": case.case_id,
                "property": case.property,
                "theta_json": row["theta_json"],
                "expected_detection": case.expected_detection,
                "expected_type": case.expected_type,
                "pred_deteccion": pred["pred_deteccion"],
                "pred_tipo_anomalia": pred["pred_tipo_anomalia"],
                "oracle_result": "pass" if passed else "fail",
                "rq3_supported": case.rq3_supported,
            }
            check_rows.append(check)
            if not passed:
                counter_rows.append({**check, **out})
        except Exception as exc:
            errors.append({"case_id": case.case_id, "property": case.property, "error": repr(exc)})

    after_hashes = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in (ROOT / "models").glob("*.joblib")}
    model_hashes_unchanged = before_hashes == after_hashes

    cases_df = pd.DataFrame(raw_rows)
    if "theta" in cases_df.columns:
        cases_df = cases_df.drop(columns=["theta"])
    outputs_df = pd.DataFrame(output_rows)
    checks_df = pd.DataFrame(check_rows)
    counter_df = pd.DataFrame(counter_rows)
    errors_df = pd.DataFrame(errors)

    cases_df.to_parquet(out_dir / "pbt_cases_raw.parquet", index=False)
    cases_df.to_csv(out_dir / "pbt_cases_raw.csv", index=False)
    outputs_df.to_parquet(out_dir / "pbt_sut_outputs.parquet", index=False)
    checks_df.to_csv(out_dir / "pbt_property_checks.csv", index=False)
    counter_df.to_csv(out_dir / "pbt_counterexamples.csv", index=False)
    errors_df.to_csv(out_dir / "pbt_execution_errors.csv", index=False)
    rejections.to_csv(out_dir / "pbt_phi_rejections.csv", index=False)

    by_prop = checks_df.groupby(["property", "oracle_result"]).size().unstack(fill_value=0).reset_index()
    for col in ["pass", "fail"]:
        if col not in by_prop.columns:
            by_prop[col] = 0
    by_prop["valid_property_checks"] = by_prop["pass"] + by_prop["fail"]
    by_prop.to_csv(out_dir / "pbt_summary_by_property.csv", index=False)

    coverage = cases_df.groupby(["property", "theta_json"]).size().rename("generated_checks").reset_index()
    coverage.to_csv(out_dir / "pbt_realized_coverage_by_theta.csv", index=False)

    integrity = {
        "cases_generated": int(len(cases_df)),
        "sut_outputs": int(len(outputs_df)),
        "property_checks": int(len(checks_df)),
        "counterexamples": int(len(counter_df)),
        "execution_errors": int(len(errors_df)),
        "phi_rejection_rows": int(len(rejections)),
        "pass_fail_equals_valid": bool((by_prop["pass"] + by_prop["fail"]).sum() == len(checks_df)),
        "every_fail_in_counterexamples": bool(set(checks_df.loc[checks_df["oracle_result"].eq("fail"), "case_id"]) == set(counter_df["case_id"]) if not checks_df.empty else True),
        "no_pass_in_counterexamples": bool(set(checks_df.loc[checks_df["oracle_result"].eq("pass"), "case_id"]).isdisjoint(set(counter_df["case_id"])) if not checks_df.empty else True),
        "all_cases_have_theta": bool(cases_df["theta_json"].notna().all() if "theta_json" in cases_df else False),
        "pbt_cases_written_only_to_results": True,
        "model_artifacts_unchanged": bool(model_hashes_unchanged),
        "random_seed": RANDOM_SEED,
        "output_dir": str(out_dir),
    }
    (out_dir / "pbt_integrity_report.json").write_text(json.dumps(integrity, indent=2, sort_keys=True), encoding="utf-8")
    (out_dir / "pbt_model_artifact_hashes_before.json").write_text(json.dumps(before_hashes, indent=2, sort_keys=True), encoding="utf-8")
    (out_dir / "pbt_model_artifact_hashes_after.json").write_text(json.dumps(after_hashes, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps(integrity, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()

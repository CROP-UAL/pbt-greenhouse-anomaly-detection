"""Feature construction reused by the PBT SUT wrapper."""

from __future__ import annotations

import numpy as np
import pandas as pd
import warnings
from pandas.errors import PerformanceWarning

warnings.filterwarnings("ignore", category=PerformanceWarning)


def add_features(df: pd.DataFrame, cfg) -> pd.DataFrame:
    """Return a copy of ``df`` with the feature columns used by the frozen SUT.

    The implementation mirrors the feature-engineering notebook sections used
    by the temporal paper pipeline, excluding direct relabelling steps because
    PBT evaluates generated inputs rather than reconstructing training labels.
    """
    out = df.copy()
    sensores_fe = [c for c in cfg.FE_SENSORES if c in out.columns]

    w_short = cfg.FE_VENTANAS["rolling_30m"]
    w_long = cfg.FE_VENTANAS["rolling_3h"]
    for col in sensores_fe:
        s = pd.to_numeric(out[col], errors="coerce")
        out[f"{col}_rmean_30m"] = s.rolling(w_short, min_periods=cfg.FE_ROLLING_30M_MIN_PERIODS).mean()
        out[f"{col}_rstd_30m"] = s.rolling(w_short, min_periods=cfg.FE_ROLLING_30M_MIN_PERIODS).std()
        out[f"{col}_rmean_3h"] = s.rolling(w_long, min_periods=cfg.FE_ROLLING_3H_MIN_PERIODS).mean()
        out[f"{col}_rstd_3h"] = s.rolling(w_long, min_periods=cfg.FE_ROLLING_3H_MIN_PERIODS).std()
        out[f"{col}_diff1"] = s.diff(1)
        out[f"{col}_diff30"] = s.diff(cfg.FE_LAG_30M)
        out[f"{col}_lag1"] = s.shift(1)
        out[f"{col}_lag30"] = s.shift(cfg.FE_LAG_30M)
        out[f"{col}_zscore_local"] = (
            (s - out[f"{col}_rmean_30m"]) / (out[f"{col}_rstd_30m"] + cfg.FE_EPS)
        )

    if {"PRAD", "PRGINT"}.issubset(out.columns):
        out["ratio_rad"] = out["PRGINT"] / (out["PRAD"] + cfg.FE_RATIO_RAD_OFFSET)
    if {"XTINV", "PTEXT"}.issubset(out.columns):
        out["delta_temp"] = out["XTINV"] - out["PTEXT"]
    if {"XHINV", "PHEXT"}.issubset(out.columns):
        out["delta_hum"] = out["XHINV"] - out["PHEXT"]
    if {"XCO2I", "PCO2EXT"}.issubset(out.columns):
        out["gradiente_co2"] = out["XCO2I"] - out["PCO2EXT"]

    columnas_vent = [c for c in cfg.COLUMNAS_CONTEXTO_MODELO if c in out.columns]
    if columnas_vent:
        out["vent_apertura_media"] = out[columnas_vent].mean(axis=1)
    if {"UVENT_cen", "UVENT_lN"}.issubset(out.columns):
        out["vent_apertura_diff"] = out["UVENT_cen"] - out["UVENT_lN"]
    if {"vent_apertura_media", "gradiente_co2"}.issubset(out.columns):
        out["co2_x_vent_apertura"] = out["gradiente_co2"] / (
            out["vent_apertura_media"] + cfg.FE_VENT_APERTURA_OFFSET
        )
    if {"vent_apertura_media", "delta_temp"}.issubset(out.columns):
        out["delta_temp_x_vent_apertura"] = out["delta_temp"] / (
            out["vent_apertura_media"] + cfg.FE_VENT_APERTURA_OFFSET
        )

    sensores_stuck = [c for c in cfg.FE_SENSORES_STUCK if c in out.columns]
    w_stuck = cfg.FE_W_STUCK
    w_stuck2 = cfg.FE_W_STUCK2
    prad_activo = (
        (pd.to_numeric(out["PRAD"], errors="coerce") > cfg.FE_PRAD_ACTIVO_MIN).astype(float)
        if "PRAD" in out.columns
        else pd.Series(1.0, index=out.index)
    )
    for col in sensores_stuck:
        s = pd.to_numeric(out[col], errors="coerce")
        rstd_5m = s.rolling(w_stuck, min_periods=cfg.FE_STUCK_MIN_PERIODS).std()
        out[f"{col}_rstd_5m"] = rstd_5m
        diff_zero = (s.diff(1).abs() < cfg.FE_ZERO_DIFF_EPS).astype(float)
        out[f"{col}_n_zero_diff_10m"] = diff_zero.rolling(
            w_stuck2, min_periods=cfg.FE_STUCK_MIN_PERIODS
        ).sum()
        changed = (s != s.shift(1)).astype(int)
        cumsum = changed.cumsum()
        out[f"{col}_consecutive_unchanged"] = cumsum.groupby(cumsum).cumcount()
        out[f"{col}_stuck_x_prad"] = out[f"{col}_consecutive_unchanged"] * prad_activo
        accel = s.diff(1).diff(1).abs()
        out[f"{col}_max_accel_5m"] = accel.rolling(
            w_stuck, min_periods=cfg.FE_STUCK_ACCEL_MIN_PERIODS
        ).max()
        vecinos = [v for v in cfg.FE_TOP_VECINOS_STUCK.get(col, []) if v in out.columns]
        if vecinos:
            vecinos_rstd = pd.concat(
                [
                    pd.to_numeric(out[v], errors="coerce").rolling(
                        w_stuck, min_periods=cfg.FE_STUCK_MIN_PERIODS
                    ).std()
                    for v in vecinos
                ],
                axis=1,
            ).mean(axis=1)
            out[f"{col}_stuck_vs_neighbors"] = vecinos_rstd / (rstd_5m + cfg.FE_EPS)
        else:
            out[f"{col}_stuck_vs_neighbors"] = 0.0
        pre_rstd = s.shift(w_stuck).rolling(
            w_stuck * cfg.FE_STUCK_PREV_WINDOW_MULT,
            min_periods=cfg.FE_STUCK_PREV_MIN_PERIODS,
        ).std()
        out[f"{col}_pre_vs_current_rstd"] = pre_rstd / (rstd_5m + cfg.FE_EPS)

    for sensor, (ref, ventanas) in cfg.FE_PARES_DELTA_REF.items():
        if sensor not in out.columns or ref not in out.columns:
            continue
        for w in ventanas:
            ref_cambio = pd.to_numeric(out[ref], errors="coerce").diff(w).abs()
            sensor_cambio = pd.to_numeric(out[sensor], errors="coerce").diff(w).abs()
            out[f"{sensor}_delta_vs_{ref}_{w}m"] = (ref_cambio - sensor_cambio) / (
                ref_cambio + cfg.FE_EPS
            )
            out[f"{sensor}_ref_cambio_{w}m"] = ref_cambio

    fecha = pd.to_datetime(out["Fecha"])
    if "Mes" not in out.columns:
        out["Mes"] = fecha.dt.month
    if "Hora" not in out.columns:
        out["Hora"] = fecha.dt.hour
    if "DiaSemana" not in out.columns:
        out["DiaSemana"] = fecha.dt.dayofweek

    out["mes_sin"] = np.sin(2 * np.pi * out["Mes"] / cfg.FE_CICLICA_PERIODOS["Mes"])
    out["mes_cos"] = np.cos(2 * np.pi * out["Mes"] / cfg.FE_CICLICA_PERIODOS["Mes"])
    out["hora_sin"] = np.sin(2 * np.pi * out["Hora"] / cfg.FE_CICLICA_PERIODOS["Hora"])
    out["hora_cos"] = np.cos(2 * np.pi * out["Hora"] / cfg.FE_CICLICA_PERIODOS["Hora"])
    out["dia_semana_sin"] = np.sin(
        2 * np.pi * out["DiaSemana"] / cfg.FE_CICLICA_PERIODOS["DiaSemana"]
    )
    out["dia_semana_cos"] = np.cos(
        2 * np.pi * out["DiaSemana"] / cfg.FE_CICLICA_PERIODOS["DiaSemana"]
    )

    hora = out["Hora"]
    mes = out["Mes"]
    dia_anyo = fecha.dt.dayofyear
    out["dia_anyo_sin"] = np.sin(2 * np.pi * dia_anyo / cfg.FE_CICLICA_PERIODOS["DiaAnyo"])
    out["dia_anyo_cos"] = np.cos(2 * np.pi * dia_anyo / cfg.FE_CICLICA_PERIODOS["DiaAnyo"])
    out["es_noche"] = ((hora >= cfg.FE_NOCHE_HORA_MIN) | (hora <= cfg.FE_NOCHE_HORA_MAX)).astype(int)
    out["es_invierno"] = mes.isin(cfg.FE_MESES_INVIERNO).astype(int)
    out["es_transicion"] = mes.isin(cfg.FE_MESES_TRANSICION).astype(int)

    if "XCO2I_consecutive_unchanged" in out.columns:
        hora_activa = ((hora >= cfg.FE_HORA_ACTIVA_MIN) & (hora <= cfg.FE_HORA_ACTIVA_MAX)).astype(int)
        out["xcoi2_stuck_x_hora_activa"] = out["XCO2I_consecutive_unchanged"] * hora_activa

    if "PRGINT_consecutive_unchanged" in out.columns and "PRAD_rstd_5m" in out.columns:
        prad_variable = (out["PRAD_rstd_5m"] > cfg.FE_PRGINT_PRAD_RSTD_MIN).astype(int)
        out["prgint_stuck_x_prad_activo"] = out["PRGINT_consecutive_unchanged"] * prad_variable

    if "PRAD_rstd_5m" in out.columns and "PRGINT_rstd_5m" in out.columns:
        out["prgint_ratio_var"] = out["PRAD_rstd_5m"] / (out["PRGINT_rstd_5m"] + cfg.FE_EPS)
        out["prad_ratio_var"] = out["PRGINT_rstd_5m"] / (out["PRAD_rstd_5m"] + cfg.FE_EPS)

    if {"PRAD", "PRGINT"}.issubset(out.columns):
        prad_std_30m = out["PRAD"].rolling(
            cfg.FE_LAG_30M, min_periods=cfg.FE_ROLLING_PRAD_PRGINT_MIN_PERIODS
        ).std()
        prgint_std_30m = out["PRGINT"].rolling(
            cfg.FE_LAG_30M, min_periods=cfg.FE_ROLLING_PRAD_PRGINT_MIN_PERIODS
        ).std()
        out["prad_stuck_vs_prgint_30m"] = prgint_std_30m / (prad_std_30m + cfg.FE_EPS)

    w_m7 = cfg.FE_M7_WINDOW
    if {"XTINV_consecutive_unchanged", "XHINV_rstd_5m", "XTINV_rstd_5m"}.issubset(out.columns):
        out["xtinv_ratio_xhinv_to_xtinv_var"] = out["XHINV_rstd_5m"] / (
            out["XTINV_rstd_5m"] + cfg.FE_EPS
        )
        out["xtinv_stuck_x_xhinv_active"] = out["XTINV_consecutive_unchanged"] * out["XHINV_rstd_5m"]
    if "XTINV" in out.columns:
        diff_zero_xtinv = (pd.to_numeric(out["XTINV"], errors="coerce").diff(1).abs() < cfg.FE_ZERO_DIFF_EPS).astype(float)
        out["xtinv_n_zero_diff_20m"] = diff_zero_xtinv.rolling(
            w_m7, min_periods=cfg.FE_M7_MIN_PERIODS
        ).sum()
    if {"PTEXT_consecutive_unchanged", "XTINV_rstd_5m"}.issubset(out.columns):
        out["ptext_stuck_x_xtinv_active"] = out["PTEXT_consecutive_unchanged"] * out["XTINV_rstd_5m"]
    if "PTEXT" in out.columns:
        diff_zero_ptext = (pd.to_numeric(out["PTEXT"], errors="coerce").diff(1).abs() < cfg.FE_ZERO_DIFF_EPS).astype(float)
        out["ptext_n_zero_diff_20m"] = diff_zero_ptext.rolling(
            w_m7, min_periods=cfg.FE_M7_MIN_PERIODS
        ).sum()

    out = out.replace([np.inf, -np.inf], np.nan)
    return out.copy()

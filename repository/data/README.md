# Data Directory

The original greenhouse dataset is not included in this replication package.

For authorized full reproduction, place the validation/campaign parquet file at
the exact implementation path expected by the scripts:

```text
data/interim/02_datos_inyectados_full_v3.parquet
```

The scripts expect the validation period to be selected internally from this
file using the configured start timestamp `2021-02-01 00:00:00`.

The file and column identifiers below are historical implementation names and
must be preserved exactly for executable reproduction.

Required variables include the timestamp and label columns:

```text
Fecha
etiqueta_deteccion
etiqueta_tipo_anomalia
```

monitored greenhouse variables:

```text
PCO2EXT, PHEXT, PRAD, PTEXT, PVV, XCO2I, PRGINT, XHINV, XTINV
```

and contextual ventilation variables used by the CA generator:

```text
UVENT_cen, UVENT_lN
```

Additional columns present in the original experimental parquet are preserved by
the full campaign but are not distributed here.

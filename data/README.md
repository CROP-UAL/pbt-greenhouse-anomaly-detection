# Data Directory

The original greenhouse dataset is not included in this replication package.

For authorized full reproduction, place the validation/campaign parquet file at
the exact implementation path expected by the scripts:

```text
data/interim/authorized_validation_campaign.parquet
```

The scripts expect the validation period to be selected internally from this
file using the configured start timestamp `2021-02-01 00:00:00`.

The column identifiers below are historical implementation names and must be
preserved exactly for executable reproduction.

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

The executable pipeline preserves the original implementation identifiers
because they are embedded in the frozen model artifacts, configuration files,
and generated results. The manuscript uses normalized paper identifiers. Use
the following mapping when relating repository artifacts to the paper:

| Implementation variable | Paper variable | Meaning |
|---|---|---|
| `PCO2EXT` | `DCO2EXT` | External CO2 concentration |
| `PHEXT` | `DHEXT` | External relative humidity |
| `PRAD` | `DGREXT` | External global radiation |
| `PTEXT` | `DTEXT` | External temperature |
| `PVV` | `DVEXT` | External wind speed |
| `XCO2I` | `XCO2INT` | Internal CO2 concentration |
| `PRGINT` | `XGRINT` | Internal global radiation |
| `XHINV` | `XHINT` | Internal relative humidity |
| `XTINV` | `XTINT` | Internal temperature |

and contextual ventilation variables used by the CA generator:

```text
UVENT_cen, UVENT_lN
```

Additional columns present in the original experimental parquet are preserved by
the full campaign but are not distributed here.

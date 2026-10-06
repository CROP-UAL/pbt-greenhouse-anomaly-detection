# Replication Package Report

Package path:

```text
v7_palmerillas_vent_null/repository
```

## Included Artifacts

- PBT implementation: `src/pbt_ist2026/`
- Conventional configuration needed by the SUT wrapper: `config/config.py`
- Frozen LightGBM artifacts: `models/*.joblib`
- Aggregate availability/campaign/post-hoc results: `results/`
- Reproducible plotting scripts and final figures: `results/.../posthoc_analysis/`, `figures/`
- Docker and local execution entry points: `Dockerfile`, `docker-compose.yml`, `Makefile`, `scripts/run_experiments.sh`
- Public validation script: `scripts/validate_repository.py`
- Documentation: `README.md`, `docs/`

## Excluded Artifacts

The package intentionally excludes the original greenhouse dataset and the
following case-level campaign artifacts:

- `pbt_cases_raw.csv`
- `pbt_cases_raw.parquet`
- `pbt_property_checks.csv`
- `pbt_counterexamples.csv`
- `pbt_sut_outputs.parquet`
- `pbt_execution_errors.csv`
- `pbt_phi_rejections.csv`

These files can be regenerated in authorized Level B reproduction mode.

## Conventional ML Evaluation Scope

The conventional ML evaluation reported in the manuscript is retained as
scientific context from the preceding supervised evaluation pipeline. The exact
final aggregate evidence needed to independently reconstruct the manuscript
performance table is not distributed in this public package.

Consequently, the package does not fabricate or infer missing conventional
evaluation artifacts. It does not include reconstructed confusion matrices,
inferred TP/TN/FP/FN counts, inferred semantic correct/error counts, or aggregate
summaries derived backwards from the percentages reported in the manuscript.
The available public artifacts should therefore not be interpreted as a full
reproduction of the conventional supervised baseline.

The public package instead focuses on the reproducibility of the PBT layer: it
includes the frozen LightGBM SUT artifacts, the PBT implementation, aggregate
PBT campaign results, post-hoc analysis outputs, and figure-generation scripts.
Full regeneration of the conventional ML baseline requires access to the
underlying greenhouse data and the original supervised evaluation context.

## Validation Performed

The following checks were executed successfully in the local environment:

```text
bash scripts/run_experiments.sh validate
```

Observed validation output:

```text
Repository validation OK
Valid property checks: 26767
Pass: 24231
Counterexamples: 2536
```

The figure-generation scripts were also executed successfully using the project
Python environment with the package-local post-hoc CSV files.

Static checks performed:

- no dataset files under `data/interim/`;
- no excluded case-level campaign files under `results/`;
- no file larger than 50 MB;
- no absolute local user paths after sanitization;
- Python scripts compile successfully.

## Docker Status

The package includes a Dockerfile and compose file. Docker could not be built in
the current execution environment because the `docker` executable is not
installed. The expected command is:

```bash
docker build -t pbt-greenhouse-anomaly-replication:latest .
docker run --rm pbt-greenhouse-anomaly-replication:latest
```

## Package Size

The final package size is approximately 24 MB, mostly due to the frozen model
artifacts in `models/`.

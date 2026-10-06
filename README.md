# PBT Replication Package for ML-Based Greenhouse Anomaly Detection

This repository contains the replication package for the empirical study
associated with the paper:

**Property-Based Testing of ML-Based Anomaly Detectors under Incomplete Ground Truth**

The package preserves the executable property-based testing (PBT) layer, the
frozen LightGBM System Under Test (SUT) artifacts, aggregate campaign results,
post-hoc analysis outputs, and figure-generation scripts used in the manuscript.

The original greenhouse dataset is **not distributed**. The package therefore
supports two reproducibility levels:

- **Level A, no private dataset:** validate the package, inspect configuration,
  inspect aggregate results, and regenerate manuscript figures from distributed
  CSV artifacts.
- **Level B, authorized dataset:** rerun the availability audit, the complete
  PBT campaign, and the post-hoc analysis after placing the authorized validation
  parquet file in the expected location.

## Repository Layout

```text
config/        Conventional pipeline configuration used by the frozen SUT.
data/          Dataset mount point; private data are intentionally absent.
docs/          Traceability, validation, and privacy notes.
figures/       Publication figures copied from the completed campaign.
models/        Frozen LightGBM SUT artifacts.
results/       Distributed aggregate campaign and post-hoc artifacts.
scripts/       Reproduction and validation entry points.
src/           PBT campaign implementation.
```

## Quick Start: Level A

Build the container and run the public validation check:

```bash
docker build -t pbt-greenhouse-anomaly-replication:latest .
docker run --rm pbt-greenhouse-anomaly-replication:latest
```

Without Docker, from this directory:

```bash
python -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
bash scripts/run_experiments.sh validate
```

The validation check confirms the distributed configuration and aggregate
results, including:

- 26,767 valid PBT checks;
- 24,231 passes;
- 2,536 counterexamples;
- no distributed private case-level campaign files.

## Regenerating Figures

Figures are regenerated only from distributed post-hoc CSV files:

```bash
bash scripts/run_experiments.sh figures
```

This does not rerun the SUT and does not require the private dataset.

## Level B: Full Authorized Reproduction

Place the authorized dataset at:

```text
data/interim/authorized_validation_campaign.parquet
```

Then run:

```bash
bash scripts/run_experiments.sh availability
bash scripts/run_experiments.sh campaign
bash scripts/run_experiments.sh posthoc
```

or, equivalently:

```bash
bash scripts/run_experiments.sh reproduce
```

The full campaign uses seed `20261001` and the frozen model artifacts in
`models/`. It does not retrain the SUT.

## Conventional ML Baseline Scope

The conventional ML baseline reported in the manuscript originates from the
preceding supervised evaluation pipeline. Full regeneration of that baseline
requires access to the underlying greenhouse data and to the original evaluation
context used for the supervised temporal validation.

This public replication package is primarily intended to preserve, inspect,
validate, and reproduce the property-based testing experimental layer. It
includes the frozen LightGBM SUT artifacts used by the PBT campaign, but it does
not distribute raw greenhouse data or retrospectively reconstructed conventional
evaluation evidence. In particular, the package does not include inferred
confusion matrices, inferred TP/TN/FP/FN counts, inferred semantic correct/error
counts, or derived conventional-evaluation summaries reconstructed backwards
from manuscript percentages.

## Important Scope Notes

The distributed aggregate results are sufficient to audit the manuscript-level
claims reported for RQ1, RQ2, and the published RQ3 figures/tables. Raw
case-level files are intentionally excluded because they contain source indices
and transformed observations derived from the private greenhouse dataset.

See:

- `docs/TRACEABILITY.md`
- `docs/VALIDATION.md`
- `docs/SECURITY_PRIVACY.md`

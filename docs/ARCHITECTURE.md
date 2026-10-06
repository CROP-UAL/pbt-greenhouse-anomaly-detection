# PBT Architecture Roadmap

This document provides a compact map of the executable PBT layer included in
the replication package. It is intended to help readers locate where each part
of the framework is implemented.

## Execution Flow

```text
authorized validation data
  -> availability audit
  -> property-specific case generation
  -> property-specific transformation
  -> frozen LightGBM SUT
  -> partial oracle evaluation
  -> aggregate results and figures
```

## Implementation Map

| Framework element | Implementation location | Role |
|---|---|---|
| Generation spaces `Theta_p` | `src/pbt_ist2026/pbt_config.py` | Defines sensors, physical ranges, duration levels, perturbation levels, contextual settings, CD pairs, PSF cardinalities, quotas, and deterministic seed. |
| Availability audit | `src/pbt_ist2026/availability_audit.py` | Counts eligible real validation contexts before executing the campaign. |
| Test-case metadata | `src/pbt_ist2026/run_pbt_campaign.py::Case` | Stores property id, theta parameters, source indices, target index, expected detection, expected type, and RQ3 support flag. |
| Case generation `G_p` | `src/pbt_ist2026/run_pbt_campaign.py::generate_cases` | Samples originally normal admissible base contexts and instantiates property-specific theta configurations. |
| Case transformation | `src/pbt_ist2026/run_pbt_campaign.py::apply_case` | Applies the concrete MV, SS, N, ORV, CA, CD, or PSF transformation to the selected observation or window. |
| Frozen SUT | `src/pbt_ist2026/run_pbt_campaign.py::FrozenSUT` | Loads frozen LightGBM artifacts, rebuilds features, applies deterministic rules, and returns observable SUT outputs. |
| Partial oracle | `src/pbt_ist2026/run_pbt_campaign.py::main` | Compares `pred_deteccion` and `pred_tipo_anomalia` with the expected property outcome and records pass/fail. |
| Post-hoc analysis | `src/pbt_ist2026/posthoc_analysis.py` | Reconstructs aggregate RQ1/RQ2/RQ3 summaries and plotting inputs from completed campaign outputs. |

## Property Locations

The seven executable properties are represented by property identifiers:

```text
MV, SS, N, ORV, CA, CD, PSF
```

Their experimental parameters are centralized in `pbt_config.py`, while their
case-generation and transformation logic is centralized in
`run_pbt_campaign.py`.

## Important Naming Note

Executable artifacts preserve historical implementation identifiers. This is
intentional: the frozen SUT, configuration files, model artifacts, hash records,
and generated results depend on exact filenames and column names. The mapping
from implementation sensor identifiers to normalized paper identifiers is
documented in `data/README.md`.

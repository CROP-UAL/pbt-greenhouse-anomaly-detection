# Traceability

This package maps the manuscript evidence to executable artifacts as follows.

| Manuscript element | Replication artifact |
|---|---|
| PBT property configuration | `src/pbt_ist2026/pbt_config.py` |
| Feature construction used by the SUT wrapper | `src/pbt_ist2026/feature_engineering.py` |
| Availability audit | `src/pbt_ist2026/availability_audit.py` |
| Frozen-SUT PBT campaign | `src/pbt_ist2026/run_pbt_campaign.py` |
| Post-hoc result extraction | `src/pbt_ist2026/posthoc_analysis.py` |
| Frozen SUT artifacts | `models/*.joblib` |
| Aggregate campaign report | `results/pbt_ist2026/campaign_20260928_150110/pbt_execution_report_by_property.csv` |
| Integrity report | `results/pbt_ist2026/campaign_20260928_150110/pbt_integrity_report.json` |
| RQ1 operationalization evidence | `results/.../posthoc_analysis/rq1_operationalization_summary.csv` |
| RQ2 property-level conformance | `results/.../posthoc_analysis/rq2_conformance_by_property.csv` |
| RQ2 failure-mode composition | `results/.../posthoc_analysis/counterexample_failure_modes_by_property.csv` |
| RQ3 SS detail | `results/.../posthoc_analysis/rq3_ss_boundary_detail.csv` |
| RQ3 N detail | `results/.../posthoc_analysis/rq3_n_boundary_detail.csv` |
| RQ3 CD detail | `results/.../posthoc_analysis/rq3_cd_boundary_detail.csv` |
| Publication figures | `figures/` and plotting scripts under `results/.../posthoc_analysis/` |
| Paper snapshot | `paper/main.tex`, `paper/references.bib` |

The authoritative executed campaign included 26,767 valid property checks:

| Property | Valid checks | Pass | Counterexamples |
|---|---:|---:|---:|
| MV | 4,500 | 4,500 | 0 |
| SS | 2,157 | 1,435 | 722 |
| N | 6,000 | 5,470 | 530 |
| ORV | 7,200 | 7,200 | 0 |
| CA | 1,500 | 1,490 | 10 |
| CD | 1,600 | 326 | 1,274 |
| PSF | 3,810 | 3,810 | 0 |

The public package does not include raw case-level campaign files. Those files
can be regenerated only in Level B mode with authorized data.


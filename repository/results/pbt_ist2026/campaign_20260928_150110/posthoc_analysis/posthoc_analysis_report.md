# PBT Post-Hoc Analysis Report

## Data Sources

- `results/pbt_ist2026/campaign_20260928_150110/pbt_cases_raw.csv`

- `results/pbt_ist2026/campaign_20260928_150110/pbt_sut_outputs.parquet`

- `results/pbt_ist2026/campaign_20260928_150110/pbt_property_checks.csv`

- `results/pbt_ist2026/campaign_20260928_150110/pbt_counterexamples.csv`

- `results/pbt_ist2026/campaign_20260928_150110/pbt_execution_report_by_property.csv`

- `results/pbt_ist2026/campaign_20260928_150110/pbt_realized_coverage_by_configuration.csv`

- `results/pbt_ist2026/campaign_20260928_150110/pbt_realized_coverage_by_theta.csv`

- `results/pbt_ist2026/campaign_20260928_150110/pbt_ss_realized_rq3_support.csv`

- `results/pbt_ist2026/campaign_20260928_150110/pbt_integrity_report.json`


## Integrity Checks

- `all_cases_have_theta`: `True`

- `cases_generated`: `26767`

- `counterexamples`: `2536`

- `every_fail_in_counterexamples`: `True`

- `execution_errors`: `0`

- `model_artifacts_unchanged`: `True`

- `no_pass_in_counterexamples`: `True`

- `output_dir`: `results/pbt_ist2026/campaign_20260928_150110`

- `pass_fail_equals_valid`: `True`

- `pbt_cases_written_only_to_results`: `True`

- `phi_rejection_rows`: `0`

- `property_checks`: `26767`

- `random_seed`: `20261001`

- `sut_outputs`: `26767`


## Campaign-Level Summary

- Total valid checks: 26767

- Pass: 24231 (90.53%)

- Fail/counterexamples: 2536 (9.47%)


## RQ1 Evidence

All seven properties were operationalized end-to-end: cases were generated, Phi-valid, executed by the SUT, and evaluated by partial oracles. No candidates were rejected by Phi_p in the completed campaign. SS used adaptive sample sizes due to independent-window availability, preserving all duration strata.

```
property  planned_checks  generated_checks  phi_valid_checks  rejected_candidates  sut_executed_checks  oracle_evaluated_checks  realized_theta_configurations  configurations_with_reduced_coverage  operationalized_end_to_end
      CA            1500              1500              1500                    0                 1500                     1500                             15                                     0                        True
      CD            1600              1600              1600                    0                 1600                     1600                              8                                     0                        True
      MV            4500              4500              4500                    0                 4500                     4500                              9                                     0                        True
       N            6000              6000              6000                    0                 6000                     6000                             75                                     0                        True
     ORV            7200              7200              7200                    0                 7200                     7200                             72                                     0                        True
     PSF            3810              3810              3810                    0                 3810                     3810                            381                                     0                        True
      SS            2157              2157              2157                    0                 2157                     2157                             40                                    22                        True
```



## RQ2 Evidence

```
property  valid_property_checks  pass  fail  conformance_rate  counterexample_rate  cr_ci95_low  cr_ci95_high
      CA                   1500  1490    10          0.993333             0.006667     0.987772      0.996375
      CD                   1600   326  1274          0.203750             0.796250     0.184734      0.224185
      MV                   4500  4500     0          1.000000             0.000000     0.999147      1.000000
       N                   6000  5470   530          0.911667             0.088333     0.904220      0.918586
     ORV                   7200  7200     0          1.000000             0.000000     0.999467      1.000000
     PSF                   3810  3810     0          1.000000             0.000000     0.998993      1.000000
      SS                   2157  1435   722          0.665276             0.334724     0.645083      0.684881
```



## Counterexample Failure Modes

```
property    failure_mode  counterexamples  property_counterexamples  percentage_of_property_counterexamples
      CA   A_binary_miss                3                        10                                0.300000
      CA B_type_mismatch                7                        10                                0.700000
      CD   A_binary_miss               16                      1274                                0.012559
      CD B_type_mismatch             1258                      1274                                0.987441
       N   A_binary_miss              501                       530                                0.945283
       N B_type_mismatch               29                       530                                0.054717
      SS   A_binary_miss              713                       722                                0.987535
      SS B_type_mismatch                9                       722                                0.012465
```



Predicted semantic types for counterexamples are stored in `counterexample_predicted_types.csv`.


## RQ3 Boundary Evidence

Boundary evidence is based on observed changes across stratified Theta_p dimensions. It should not be reduced to global property conformance. ORV, MV, and PSF showed no failure boundary within the exercised spaces. SS, N, CA, and CD require stratified reading; SS strata with `n < 20` are retained but flagged as limited support for quantitative boundary claims.


Detailed boundary evidence rows are stored in `rq3_boundary_summary.csv`.


## Relation To Conventional ML Baseline

The conventional baseline reported in the manuscript is binary accuracy 99.20%, precision 96.75%, recall 97.15%, F1 0.9695, and multiclass anomaly-type accuracy 97.07%. The PBT campaign is not a replacement test-set metric. It shows that high aggregate conventional performance can coexist with heterogeneous property conformance: MV, ORV, and PSF conform in all exercised cases, while CD, SS, N, and CA expose localized counterexamples under property-defined conditions.


## Limitations

- The analysis uses the completed campaign only and does not rerun the SUT.

- CD severity is a post-hoc analytic stratification derived from reference-variable percentiles; it is not an extension of Theta_CD.

- SS long-duration strata with `n < 20` are executed and retained but should not alone support quantitative boundary claims.

- The SUT was loaded in the available local environment; prior execution recorded scikit-learn version warnings, while model hashes remained unchanged.


## Candidate Tables And Figures

- Table: RQ1 operationalization summary.

- Table: property-level conformance with Wilson 95% intervals.

- Heatmap: SS conformance by sensor and duration, marking `rq3_supported`.

- Line/small multiples: Noise conformance by magnitude, sensor, and direction.

- Table/heatmap: CD conformance by pair, side, and severity.

- Bar chart: failure modes by property and predicted type for counterexamples.

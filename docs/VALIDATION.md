# Validation

Run:

```bash
bash scripts/run_experiments.sh validate
```

This validation requires no private dataset. It checks:

1. The planned PBT configuration in `pbt_config.py`.
2. The expected deterministic seed `20261001`.
3. The PSF combinatorial coverage for cardinalities 4--8.
4. Property-level aggregate results for the completed campaign.
5. Campaign integrity flags recorded during execution.
6. RQ3 detail-file row counts and totals.
7. Absence of intentionally excluded private/case-level campaign files.

Expected output:

```text
Repository validation OK
Valid property checks: 26767
Pass: 24231
Counterexamples: 2536
```

Full reproduction with authorized data additionally requires:

```bash
bash scripts/run_experiments.sh availability
bash scripts/run_experiments.sh campaign
bash scripts/run_experiments.sh posthoc
```

The campaign writes new results under `results/pbt_ist2026/campaign_<timestamp>/`
and preserves hashes of the frozen model artifacts before and after execution.


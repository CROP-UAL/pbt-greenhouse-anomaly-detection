# Security And Privacy Notes

The public package intentionally excludes:

- the original greenhouse dataset;
- raw transformed PBT cases;
- SUT output files at case level;
- property-check files with case identifiers;
- counterexample files at case level;
- execution files that may expose source indices.

Distributed results are aggregate/post-hoc artifacts sufficient to audit the
reported manuscript evidence without exposing the source dataset.

The `.gitignore` blocks the main private-data paths and the excluded case-level
campaign outputs. Before public release, run:

```bash
bash scripts/run_experiments.sh validate
```

and optionally inspect:

```bash
find . -type f -size +50M
```

to confirm that no unintended large data files have been added.


# Local benchmarks

Store benchmark repositories and data here. Downloaded data is ignored.
`issuetrojan/` contains the maintained GitHub issue adapter.

CodeIPI is maintained in [inspect_evals](https://github.com/UKGovernmentBEIS/inspect_evals).
We keep only its `src/inspect_evals/ipi_coding_agent/` benchmark directory using
Git sparse checkout, along with root and ancestor-directory files.

Expected local layout:

```text
benchmarks/
├── README.md
└── inspect_evals/
    └── src/inspect_evals/ipi_coding_agent/
```

From the project root, with the Conda environment active:

```bash
git clone --depth 1 --filter=blob:none --sparse \
  https://github.com/UKGovernmentBEIS/inspect_evals \
  benchmarks/inspect_evals
git -C benchmarks/inspect_evals sparse-checkout set \
  src/inspect_evals/ipi_coding_agent
```

Do not install the sparse checkout as a package: its registry imports other
benchmarks. Run `python -m scripts.run_codeipi PROVIDER/MODEL` from the project
root, or set the model in `configs/default.yaml`. The script loads the task file
directly and sets `PYTHONPATH` for
its package imports. Keep the entire CodeIPI directory, including dataset and
Docker files. See the project README for Conda and Docker setup.

Record the benchmark commit (`git -C benchmarks/inspect_evals rev-parse HEAD`)
alongside results so runs can be reproduced. See the upstream
[CodeIPI README](https://github.com/UKGovernmentBEIS/inspect_evals/blob/main/src/inspect_evals/ipi_coding_agent/README.md)
for dataset, sandbox, and scoring details.

## IssueTrojanBench

Run `python scripts/fetch_issuetrojan.py` from the project root. It verifies the
Zenodo archive checksum and extracts into `benchmarks/issuetrojan-data/issuetrojanbench`.
The adapter verifies all 31 consumed script, payload, and scorer hashes.
`SOURCE_COMMIT` identifies the KavachBench reference source, not the data release.

`python -m scripts.run_issuetrojan --list` lists all 144 GitHub issue cases.
Case names use `seed:attack:perturbation`. Use `--seeds` or exact `--samples`
to limit a run. All six released seeds and their four attacks are supported.
The variants preserve released English, Chinese, uppercase, position, and
visible or HTML-comment text. The adapter reads constants without importing
or running issue-publishing scripts. No issues are published.

The runner uses the repository and commit choices in
[the seed mapping](../docs/issuetrojan-seed-revisions.md). The released executable
EEM rules check file existence only. Task correctness is deferred. See the
[project README](../README.md) for Docker, configuration, and tracing setup.

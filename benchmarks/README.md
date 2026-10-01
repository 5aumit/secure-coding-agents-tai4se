# Local benchmarks

Store benchmark repositories and data here. Everything except this README is
gitignored.

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
benchmarks. Run `bash scripts/run_codeipi.sh PROVIDER/MODEL` from the project
root instead. The script loads the task file directly and sets `PYTHONPATH` for
its package imports. Keep the entire CodeIPI directory, including dataset and
Docker files. See the project README for Conda and Docker setup.

Record the benchmark commit (`git -C benchmarks/inspect_evals rev-parse HEAD`)
alongside results so runs can be reproduced. See the upstream
[CodeIPI README](https://github.com/UKGovernmentBEIS/inspect_evals/blob/main/src/inspect_evals/ipi_coding_agent/README.md)
for dataset, sandbox, and scoring details.

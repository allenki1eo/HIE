# benchmarks/results

Local, never-committed experiment outputs. Each run creates
`<EXPERIMENT>/<UTC timestamp>_<label>/` with an `experiment.json` (commit, dirty flag,
parameters, environment) and refuses to reuse an existing directory. Summaries worth
keeping are copied into `benchmarks/reports/`.

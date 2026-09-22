# benchmarks/

- `scripts/` — thin entry points. Everything runs through the `hie` CLI, so benchmarks are reproducible from a commit.
- `metrics/` — the metric code lives in the importable package `hie_core/metrics/`. This folder documents it.
- `reports/` — committed summaries (JSON and Markdown) copied from runs, with the commit that produced them.
- `results/` — local run directories (git-ignored), never overwritten.

```bash
hie bench synthetic --split test     # EXP-001…005 with ground truth
hie bench hdrplus                    # all local HDR+ bursts + HTML report
```

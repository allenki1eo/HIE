# Contributing to HIE

Hanson Image Engine is open for outside contributions under the
[Apache License 2.0](LICENSE). There is no separate contributor licence
agreement. A pull request is a contribution under that licence
([Apache 2.0, section 5](https://www.apache.org/licenses/LICENSE-2.0)).

Please read the [code of conduct](CODE_OF_CONDUCT.md) before participating.

## What helps

- Bug fixes and tests for the v0.1 pipeline, the dataset loader, and Camera Lab.
- Reproductions of published methods, with the paper named and the difference recorded.
- Negative results. If a method loses to a baseline, that belongs in `docs/benchmark.md`.
- Documentation that points at a run directory and a git commit for every number.

## What stays gated

Do not add an algorithm described as novel, first, or state of the art until
the project owner approves the current research report (`docs/research-report-*.md`).
Hypothesis H1 is not approved. Do not implement it in the Python engine or the
Android app.

Do not commit datasets, DNGs, or generated image collections. The Google HDR+
burst set is CC BY-SA and is downloaded locally; keep its attribution wherever
its images appear. Never modify files under `datasets/` except the README files
that are already tracked.

## Setup

Python 3.10 or newer:

```bash
pip install -e ".[dev]"
python -m pytest -q          # skip slow tests with: -m "not slow"
```

`realdata` tests skip themselves when no HDR+ burst has been downloaded.

Android Camera Lab needs JDK 17 and Android SDK 34. See [android/README.md](android/README.md).

## Research rules

These match [AGENTS.md](AGENTS.md) and [docs/research-plan.md](docs/research-plan.md).

- Pixel values are float32 in the normalised linear raw domain (black 0, white 1) until `pipeline.render`.
- Flow is `flow[y, x] = (dx, dy)` from the reference to the alternate frame. Warping samples the alternate at `x + flow`.
- The loader must not drop frames silently. Exclusions are explicit and written into the run notes.
- Tune on the synthetic `tune` split or on held-out bursts. Evaluate on `test`. Never tune on evaluation data. Split learned models by burst or scene, never by frame.
- Prefer a physical model and classical reconstruction. Do not add generative detail without a justified experiment.
- Fill `docs/prior-art.md` only from sources you actually opened. Use `?` when a field is unverified, and append the search to the search log.
- Experiments that you intend to report go through `hie bench` or `hie process`, which create a new run directory and an `experiment.json` with the git commit. Commit the code before that run.

## Pull requests

1. Fork the repository and branch from the default branch.
2. Keep the change focused. One concern per pull request.
3. Add or update tests for behaviour you change.
4. Fill in the pull request template, including the licence confirmation.
5. Do not force-push over a review unless a maintainer asks you to.

Maintainers are Hanson Technologies ([@allenki1eo](https://github.com/allenki1eo)).
Review can take time; a failing test or a missing prior-art note is the usual reason a change waits.

## Reporting issues

Use the GitHub issue templates. Include the command, the commit, and the run
directory when a number or a failure is involved. Security reports go through
[SECURITY.md](SECURITY.md), not a public issue.

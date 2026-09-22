# AGENTS.md — rules for coding and research agents working on HIE

HIE is a computational photography **research** project. Read `docs/research-plan.md` first.

## Non-negotiable research rules
- Never write "novel", "first", "state of the art" or "new algorithm" without the novelty
  protocol in the brief: exact search, synonyms, combinations, papers, patents, code, closest prior art,
  documented differences, experiment, benchmark. Record every search in `docs/prior-art.md#search-log`.
- Fill `docs/prior-art.md` only from sources you actually opened. Use `?` when unverified.
- Record negative results. If an HIE method loses to a baseline, write that down in `docs/benchmark.md`.
- **Approval gate:** do not implement an allegedly novel algorithm until the owner approves the current
  research report (`docs/research-report-*.md`).
- Tune parameters on the synthetic `tune` split or on held-out bursts, and evaluate on `test`.
  Never tune on evaluation data. For learned models, split by burst or scene, never by frame.
- Prefer physics + classical reconstruction + small learned parts over black boxes.
  Recover before hallucinating: no generative detail without a justified experiment.

## Data rules
- Never commit datasets, DNGs or generated image collections (`.gitignore` enforces most of this).
- Never modify files under `datasets/`. Keep Google HDR+ attribution (CC BY-SA) wherever its images appear.
- The loader must never drop frames silently. Exclusions are explicit and recorded in run notes.

## Engineering
- Install: `pip install -e ".[dev]"`. Test: `python -m pytest -q` (`-m "not slow"` for a quick run;
  `realdata` tests skip without downloaded bursts).
- Everything is float32 in the normalised linear raw domain (black 0, white 1) until `pipeline.render`.
- Flow convention: `flow[y, x] = (dx, dy)` maps reference → alternate; warping samples the alternate at `x + flow`.
- Experiments go through `hie bench …` / `hie process …`, which create new run directories and an
  `experiment.json` with the git commit. Commit before running experiments you intend to report.
- Keep numbers in docs traceable: say which run directory (commit) they came from.

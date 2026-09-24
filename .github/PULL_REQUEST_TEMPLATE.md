## Summary

<!-- What changed, and why. Link the issue if there is one. -->

## Checks

- [ ] `python -m pytest -q` (or `-m "not slow"`) passes locally
- [ ] Android changes were built with `./gradlew :app:assembleDebug :app:test` when `android/` changed
- [ ] No datasets, DNGs, or generated image collections are committed
- [ ] Numbers in docs name the run directory and commit they came from

## Research

<!-- Delete this section if the change is engineering only. -->

- [ ] This does not implement hypothesis H1 or another unapproved method
- [ ] Prior-art notes were filled only from sources I opened (`docs/prior-art.md`)
- [ ] Parameters were not tuned on the evaluation split

## Licence

I license this contribution under the Apache License 2.0, the licence of this
repository. I have the right to submit it.

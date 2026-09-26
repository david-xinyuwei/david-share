# About this repository

`README.md` is **generated**. Do not edit it by hand; edit `render.py` or re-run a measurement.

```
render.py          one file: run directory in → README.md + images/ out; --check diffs against the committed README
pricing.json       list prices with a verified-on field; cost prints only when verified
testpack/          what the tester runs on their own machine (runner, prompts, .env.example)
runs/<name>/       one frozen measurement: results JSON, attempts log, images, source/ (runner + prompts as run)
images/            round-1 images copied out of the run, SHA-256 verified against the run record
tests/             seven contracts on the rendered README: check-mode passes, sections in order, prompts quoted verbatim,
                   medians match raw data, every image exists and matches its recorded hash, no GUIDs or keys, no cost for
                   unverified prices
```

Why so small: the earlier benchmark repo grew to 179 KB of README and 18 sections because every follow-up landed as a new
section. This one has one question — *against US-region deployments, how long does each configuration take and what does it cost
per image* — one table that answers it, the images so a reader can judge quality for themselves, and a method block. Anything
else belongs in the run directory, not the README.

Adding a new run: drop the run directory under `runs/`, `python render.py runs/<name>`, commit README + images together.
`tests/run_tests.ps1` runs the suite and writes `tests/last-run.txt`.

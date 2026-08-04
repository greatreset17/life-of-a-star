# The Life of a Star

The Sun's entire life — protostellar contraction to cold black dwarf — with every
colour derived from published data, never chosen. Three stages:

- **Stage −1 (`harness/`)** — the verification harness. Built first. Physics mirror
  (independent numerics, headless), visual gate (Playwright captures, each with a
  mandatory state probe), identity hashing of the Stage 0 output.
- **Stage 0 (`pipeline/`)** — offline Python pipeline. Acquires published data against
  a checksummed manifest and emits the derived tables Stage 1 consumes. No fallbacks:
  a source that cannot be obtained stops the pipeline by name.
- **Stage 1 (`app/`)** — the browser experience. Fetches nothing at runtime; all
  physics arrives as local data files from Stage 0.

The canonical record of every decision fork is the comment block at the head of
`pipeline/constants.py` — not this file, not the prompt.

## Running the harness

```
.venv/bin/python harness/run.py selftest      # physics-mirror known-answer tests
.venv/bin/python harness/run.py static        # static checks over shipping source
.venv/bin/python harness/identity.py record|verify <label> <dir>
node harness/gate.mjs <appdir> <label>        # visual gate: captures + state probes
```

The mirror is a second implementation: where Stage 0/Stage 1 compute a quantity, the
mirror computes it independently and disagreement is the signal. Where the shipped
source can be executed directly (Stage 1 JS modules under Node), the harness runs the
shipped source rather than a reimplementation — a drifted mirror is worse than none.

## Passes

v0.0 harness · v0.1 spine · v0.2 Earth · v0.3 death · v0.4 sky. Each pass is a commit,
its test subset green, its Stage 0 identity hash recorded in `harness/hashes.json`.

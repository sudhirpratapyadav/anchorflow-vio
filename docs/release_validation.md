# Source release validation — 2026-10-17

The release was checked on Ubuntu 22.04 / Intel Core i7-10700, using the existing
read-only vcpkg dependency cache and fresh native source/object files. It did not
copy the historical Basalt executable or estimator library. A fully fresh
network dependency installation was not tested; the public build path and its
limitations are documented in [build.md](build.md).

## Native reproduction

- Reconstructed pinned upstream Basalt plus the exact historical F29 patch.
- Compiled all 43 native targets with one worker under a 4 GiB memory limit.
- Prepared the first 800 Short19 images using the portable release preparer.
- IMU CSV, image CSV and image timestamp list match the original smoke input
  byte for byte; native calibration JSON is semantically identical.
- Ran the rebuilt native executable through `scripts/run_sequence.py` in a fresh
  Python 3.10 environment containing only the pinned NumPy inference dependency.
- Both `trajectory.txt` and submission `estimate.txt` match the original frozen
  runtime's smoke output **byte for byte**.
- All 800 image timestamps are covered: 780 native poses, 20 initialization
  fills, zero later fills. All 139,977 observations are from camera 0.

This is a 40-second installation/reproduction check, not a repeat of the ten
full-record accuracy experiments. Historical per-record metrics remain labeled
as such. Different compiler/CPU/dependency combinations can change behavior;
byte-identical results are claimed only for the tested setup.
The [native validation receipt](../native/validation.json) records runtime hashes,
observation parity and measured resource use.

## Python and submission checks

Nine unit tests pass in the fresh inference environment. They cover one-camera
calibration construction, unknown-calibration rejection, runtime path safety,
missing/duplicate/reversed timestamps, malformed poses, deterministic archives,
tampering, cropped runs, wrong dataset-split labels and mixed native configs.

The actual 800-frame smoke is rejected by the full-record manifest generator:
`ValueError: Only full-record runs may be submitted`. This is the expected
negative test, not an inference failure.

The ten original full-record training trajectories were repackaged as
`anchorflow-vio-training10.zip`. All 265,694 poses pass the official LaMAria
trajectory parser and local format checks. Every archived trajectory is
byte-identical to the original frozen training archive. ZIP ordering changed,
so the new archive has its own SHA-256:

```text
e7a3e5384bfb39a4fbada5a2ad5fb7723df3511a992cc42bba6b210a5de0429d
```

The public [package receipt](../benchmarks/training_package.json) lists the
per-record pose counts and hashes. Format validation does not repair Platform12
or imply main-test coverage. The archive itself is a local deliverable, not
embedded in this source repository.

## Release boundaries

Only the mono source adaptation, configuration, tooling, benchmark summaries
and dependency notices are published. No dataset, private research history,
credentials, binary cache or stereo experiment tree is included. No main-test
data was downloaded and no leaderboard upload was performed. The official test
index was inspected only to prepare the documented data/storage plan.

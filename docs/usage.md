# Running AnchorFlow

Use Linux, Python 3.10 or newer, and the native runtime built using [build.md](build.md).
Commands below run from the repository root. No dataset is included or downloaded
automatically. Install the small inference dependency set in a separate environment:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
```

## Input layout and calibration

Supply a LaMAria sequence directory containing `asl_folder/`,
`aria_calibrations/` and `pinhole_calibrations/`. Ground truth is unnecessary for
inference. The ASL directory must contain exactly one `imu0/data.csv` and its
sibling `cam0/data.csv` and `cam0/data/`. The preparer does not expose cam1 to the
native process. Use the undistorted ASL images with their pinhole calibration.

```sh
.venv/bin/python scripts/prepare_input.py /data/sequence_1_19 --check
.venv/bin/python scripts/prepare_input.py /data/sequence_1_19 outputs/sequence_1_19/input
.venv/bin/python scripts/run_sequence.py outputs/sequence_1_19/input outputs/sequence_1_19/run --runtime build/native/runtime
```

Every output directory must be new. On a small machine, run only one native worker
at a time; the default estimator uses two threads. A systemd user service with
`MemoryMax=4G` and a timeout can bound resources. If limiting CPU usage, verify that
the host actually enforces its CPU controller, or use `taskset` with two available
logical CPUs. The validation host used CPUs 14 and 15; those IDs are not portable.

The factory IMU coefficients in `configs/factory_imu/` cover the two calibration
hashes used in the measured training set. Their model is
`rectified = inverse(M) * (raw - bias)`. These sensor coefficients were recovered
from Project Aria factory calibration; they are not ground-truth trajectory fits.
The historical lookup key is the first eight hex digits of the Aria calibration
file's MD5. Unknown keys fail explicitly. Use `--factory-dir` to supply a verified
coefficient set for another calibration; do not rename a file or substitute an
identity matrix to bypass this check. Test-device compatibility is unverified.

The preparer preserves the measured 4.2 ms IMU timestamp subtraction and noise
settings. It creates image symlinks, so the source images must remain available.
Its manifest fingerprints the sensor CSVs, calibrations and generated files;
individual image bytes are not hashed. It does not load reference poses.

## Outputs and timing

- `trajectory.txt`: native estimated poses in TUM format.
- `estimate.txt`: `world_from_imu` poses at every requested image timestamp,
  formatted for LaMAria.
- `coverage.json`: native matches and initial/later pose fills.
- `sensor_audit.json`: verifies every dumped observation uses camera zero.
- `native.log`, `time.txt`, `run_info.json`, `result.json`: execution, resource use
  and file fingerprints.

Initial frames receive the first available pose; later gaps carry a previous
estimate. Full timestamp coverage does not imply valid tracking or accuracy.
The original Platform12 run is a documented counterexample. Observation dumps
are retained for auditing and are included in the reported native runtime cost.

For a short installation smoke, add `--max-frames 800` to preparation. Such cropped
runs are explicitly rejected by the submission manifest generator and packager.

## Evaluation

See [evaluation.md](evaluation.md) for the optional official evaluator environment.
Inference itself requires neither ground truth nor the evaluator dependencies.

```sh
.venv-eval/bin/python scripts/evaluate.py outputs/sequence_1_19/run/estimate.txt /data/sequence_1_19 \
  --aria-calib /data/sequence_1_19/aria_calibrations/sequence_1_19.json \
  --out-dir outputs/sequence_1_19/evaluation
```

Use the actual calibration filename from your download. Metrics with unavailable
ground truth remain absent/null; do not replace them with zero. Preserve failed
control-point alignments as failures.

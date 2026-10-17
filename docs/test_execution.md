# Frozen test execution

`scripts/fetch_test_data.py` downloads the approved test cohort independently.
`scripts/run_test_queue.py` consumes only atomic `.download_complete.json`
receipts under `ROOT/data/test/<sequence>`. It processes numeric category and
sequence order among currently ready recordings, with one estimator at a time.
Inference begins only after a successful full Short19 training reproduction
receipt for the same source-built runtime. No test ground truth is available;
there are no accuracy scores, configuration sweeps or test-based tuning.

Start the downloader separately, on a filesystem with enough free space:

```sh
systemd-run --user --unit=anchorflow-test-download \
  --property=MemoryMax=1G --property=Nice=15 --property=LimitCORE=0 \
  --property=RuntimeMaxSec=1209600 --working-directory="$PWD" \
  /usr/bin/taskset -c 12,13 /usr/bin/python3 scripts/fetch_test_data.py \
  /path/to/external/test-root
```

It fetches all 63 ASL archives and both calibration JSONs per recording. Partial
archives resume only while the remote length/ETag/last-modified identity matches.
All members are CRC-checked during extraction and SHA-256 hashes are recorded in
`extracted_files.jsonl`. Unsafe archive paths and symbolic links are rejected.
The original cam0 CSV and image coverage are checked before the directory and
its readiness receipt become visible to inference. Only then is the owned ZIP
deleted; extracted camera/IMU data, checksums, transfer logs and provenance remain.

Inspect `download_status.json` for live byte counts, transfer PID and failures.
Downloads are serial and independent of native inference, keeping archive
duplication and disk pressure bounded. Twenty GiB of free-space reserve is kept;
extraction checks the archive's declared uncompressed size before writing. The
service can be restarted after inspection to resume partial downloads and skip
verified ready directories. It never deletes another project's files.

Run the queue in a bounded service (choose CPU IDs available on the host):

```sh
systemd-run --user --unit=anchorflow-test-inference \
  --property=MemoryMax=4G --property=CPUQuota=200% --property=Nice=15 \
  --property=LimitCORE=0 --working-directory="$PWD" \
  --setenv=OPENBLAS_NUM_THREADS=1 --setenv=OMP_NUM_THREADS=1 \
  /usr/bin/timeout 1209600 /usr/bin/taskset -c 14,15 \
  "$PWD/.venv/bin/python" scripts/run_test_queue.py \
  --root /path/to/external/test-root --runtime /path/to/native/runtime \
  --training-proof /path/to/full_short19_parity.json
```

The native worker also retains the frozen four-hour per-record timeout. The
service-level fourteen-day limit bounds the waiting queue; restart after review
if downloads require longer. Inspect `queue_status.json`, per-record `logs/`,
`runs/<sequence>/native.log`, `run_info.json`, `time.txt`, and `queue_audit.json`.
The status records exact queue commands, source/runtime hashes, native timing,
failures, coverage, camera audit and motion diagnostics. Stop with
`systemctl --user stop anchorflow-test-inference.service`; systemd terminates its
whole process group. No other project's services are touched.

The queue holds an exclusive filesystem lock, pins inference tools/configuration
and runtime bytes, and verifies completed records on restart. Failed/interrupted
native runs and existing partial output are not retried automatically. Review
errors explicitly before making a separate recovery plan; never replace a test
trajectory with a per-record winning configuration. A changed scientific source
pin causes a hard stop. Downloader changes do not change inference pins.

Every output is checked against timestamps independently read from the complete
original cam0 CSV, including original image existence, monotonicity, finite
positions, unit quaternions, and exact coverage. Native observation bytes must
contain only camera0 and finite image coordinates. Prepared-file hashes and run
provenance are checked again. Motion step/speed extremes and initialization fills
are diagnostics, not accuracy claims or automatic reasons to select a different
configuration. A format-valid trajectory may still have severe drift or tracking
failure, especially given the known training Platform failure.

After every completed category, the queue writes a single-policy pinned manifest
and deterministic validated ZIP under `packages/category_N`; when all63 finish,
`packages/all_63` is generated. These are local files only. The queue uses the
release format validator; a final official LaMAria parser check can be run in an
environment with `lamaria` installed, using a fresh output directory:

```sh
python scripts/package_submission.py /path/to/test-root/packages/all_63.json \
  /path/to/test-root/packages/all_63_official --official-parser
```

No command here uploads or submits. Failed or unavailable records remain explicit
in status and prevent a complete category/final package.

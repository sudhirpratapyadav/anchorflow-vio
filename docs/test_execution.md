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
and deterministic validated ZIP under `packages/category_N`; when all 63 finish,
`packages/all_63` is generated. These are local files only. The queue uses the
release format validator; a final official LaMAria parser check can be run in an
environment with `lamaria` installed, using a fresh output directory:

```sh
python scripts/package_submission.py /path/to/test-root/packages/all_63.json \
  /path/to/test-root/packages/all_63_official --official-parser
```

No command here uploads or submits. Failed or unavailable records remain explicit
in status and prevent a complete category/final package.

## Full training parity before test inference

On 2026-10-17, the source-built runtime reproduced the complete Short19 training
recording: all 18,352 output poses, the native trajectory, and all 18,352 observation
files were byte-identical to the frozen original. The observations contain
2,948,425 camera0 measurements. Coverage has 20 initial fills and 1 terminal fill,
matching the original. Native execution used 373.30 CPU seconds, 211.13 wall seconds
and 199,668 KiB peak RSS.

The first preparation attempt stopped before inference because the corrected
IMU ended 4.804362 ms before the final image. The release preflight now reports
sub-frame endpoint gaps while preserving every original image/IMU row; it still
rejects gaps exceeding one median image period. Fresh full-record camera CSV,
corrected IMU CSV and image timestamps matched the historical input bytes, and
calibration values matched. This preflight correction changes no estimator
configuration or sensor samples. The external execution proof is
`validation/full_short19_parity.json` under the selected test root.

## Interrupted transfer recovery

During sequence_1_5 on 2026-10-17, curl reported SSL error 56 (unexpected EOF).
Its internal retry rewound the partial download to the initial invocation offset,
losing roughly 3.45 GB of transfer progress. The downloader now retries with a
fresh curl process, rechecks remote identity, and resumes from the current file
size on each attempt. It permits nine attempts with ten seconds between them.
A regression test checks partial-byte preservation, remote rechecking and disabled
internal curl retries. All 21 tests pass. The downloader service was recreated
with its original resource limits; the inference queue remained running and no
scientific configuration changed. Completed recordings were preserved.

### Parallel archive downloads (2026-10-18)

Owner authorized aria2c parallel downloads. The downloader now supports opt-in `ANCHORFLOW_PARALLEL_DOWNLOADS=1`: four connections for new ZIP archives, 32 MiB disk cache, and resumable aria2 control files. Existing contiguous curl partials finish through curl. Full logical file size is never treated as completion while an aria2 control file exists; progress bytes are null during segmented transfers (see the transfer log). Remote identity, ZIP CRC/file ledger, layout checks and atomic readiness publication remain required. Download service restarted with the option enabled; inference queue unchanged. Validation: 22 unit tests passed, including full-size incomplete segmented-file resume. GitHub push remains deferred until final release.

### Host restart recovery (2026-10-18)

The host booted at 20:22:23 IST, leaving both transient services inactive.
At recovery, 41 datasets were ready and 40 trajectories were complete. All frozen
source/config/runtime hashes matched the saved queue pins. Sequence_3_13 had
partial native observations but no final trajectory or result; its input, run,
log and prior queue state were preserved under
`interrupted_attempts/sequence_3_13_1792335595` in the external test root.
The interrupted record was removed from the pending queue state for a fresh run
with the identical frozen method; completed records were retained. Both services
were recreated with their original CPU and memory limits. Sequence_3_14 resumed
from its aria2 control file. Queue startup independently reaudits completed runs.
This is recovery from an interrupted execution, without configuration selection
or test-set tuning. All 40 completed trajectories passed the official parser.
The Medium category archive also passed official-parser packaging; SHA-256:
`34674650d1e347cd8b8776854aa1ebacc6e61f9646b4734e256bbee8dd786dfc`.
No upload or GitHub push was performed.

### Long category complete (2026-10-18)

All 16 Long test trajectories completed with the frozen method. The final run,
sequence_3_16, exited successfully and produced 45,040 poses with full original
image timestamp coverage; the official parser accepted it. All 44 Short, Medium
and Long trajectories now have individual official-parser validation receipts.
The Long category ZIP passed official-parser packaging with all 16 required
recordings: `packages/category_3_official/anchorflow_mono_category_3.zip` under
the external test root. SHA-256:
`134d4e8a9fa1ad37a79f0b9570584b32f49e6668a1da05927e17a368596d0721`.
Manifest SHA-256:
`7abb043d2efd284ebaca6423c56820e76ac1a65045a4b732883cdf97cf14361f`.
These checks certify format and coverage, not hidden-test accuracy. At this
checkpoint 45 datasets were ready, sequence_4_1 was processing and sequence_4_2
was downloading. Lowlight and Platform remain outstanding. No upload or GitHub
push was performed.

## Low-light category complete (2026-10-19)

All nine low-light test trajectories passed the official parser, image-count coverage and estimate SHA checks. The category package is `packages/category_4_official/anchorflow_mono_category_4.zip` under the external-drive test root. Archive SHA-256: `7f105b931e32428c5ed82fb8618957b60e3045e2f47a1ed2cb5cad8535c768c4`; manifest SHA-256: `ed5a8c3943c0e99ee4a98967a3a380d4eb932b82e52ba2c4585e374f6db905ef`. All 53 trajectories across Short, Medium, Long and Low-light are complete. The ten moving-platform sequences remain; sequence_5_1 is downloading. These checks establish format and coverage, not hidden-test accuracy. No upload performed.

### Platform progress and motion diagnostics (2026-10-19)

The first five Platform recordings completed with the frozen method and passed
individual official-parser, expected-image-count and estimate SHA-256 checks:
47,921, 38,795, 49,266, 33,509 and 42,253 poses for sequence_5_1 through
sequence_5_5 respectively. This brings individually validated trajectories to 58.
At this checkpoint 60 datasets were ready, sequence_5_6 was processing and
sequence_5_8 was downloading.

Format and coverage success do not imply successful tracking. The existing queue
motion audit reports severe discontinuities on sequence_5_4 (maximum consecutive
step 181.23 m; 26,823 steps over 10 m) and sequence_5_5 (125.07 m; 24,530 steps
over 10 m). These are material reliability limitations of the frozen submission,
not accuracy scores. Sequence_5_3 has a maximum step of 0.130 m and no steps over
10 m. Preserve all outputs and report these diagnostics; do not select runs,
change parameters, or repair trajectories based on hidden-test behavior.
No leaderboard upload or final GitHub push has been performed.

### Sixth Platform trajectory validated (2026-10-19)

Sequence_5_6 passed the official parser and original image-count/SHA checks with
49,728 poses. Its motion audit reports a maximum consecutive step of 108.61 m
and 28,988 steps over 10 m, extending the observed Platform tracking limitation.
Estimate SHA-256: `adbaafb4cca90cc359f1030c441adace10714f7d5f807f4667445cb925085856`.
There are now 59 individually validated trajectories and 61 ready datasets;
sequence_5_7 is processing and sequence_5_9 is downloading. All outputs are
preserved from the frozen configuration. Hidden-test accuracy is unknown.

### All test datasets downloaded (2026-10-19)

All 63 approved ASL test datasets now have completed download records and atomic
readiness markers on the external drive. The downloader exited after finishing
the final sequence_5_10 extraction. Inference remains active on sequence_5_9,
with sequence_5_10 next. Individual official-parser receipts cover 61 completed
trajectories, including sequence_5_7 (24,745 poses, maximum step 0.1454 m) and
sequence_5_8 (25,360 poses, maximum step 0.1484 m). Final Platform/all-sequence
packaging, completion audit and GitHub update remain pending.

### All inference and packaging complete (2026-10-19)

All 63 trajectories passed individual official-parser and coverage/SHA checks.
Sequence_5_10 produced 31,924 poses with maximum consecutive step 0.3084 m.
The five category ZIPs and combined 63-recording ZIP passed official-parser
packaging, CRC and exact estimate-content checks. The final audit receipts are
`validation/final_63_audit.json` and `validation/final_packages.json` under the
external root. All 22 Python tests passed. See [test_completion.md](test_completion.md)
for package hashes, paths and the observed Platform tracking limitations.
No leaderboard upload performed.

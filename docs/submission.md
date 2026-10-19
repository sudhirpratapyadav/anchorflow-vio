# LaMAria submission

Source: [official submission documentation](https://lamaria.ethz.ch/slam_documentation).
The website evaluates both training and test outputs. Training uploads do not
establish a main-test leaderboard result. Test uploads make a method public, as
described by the method-creation form. A challenge ranking requires all its test
sequences; the site permits partial uploads and limits test updates to 24 hours
after the previous successful evaluation. Tune only on training data.

## Suggested method form

| Field | Value |
|---|---|
| Short name | AnchorFlow VIO |
| Full name | AnchorFlow Visual-Inertial Odometry |
| Image input | Monocular |
| IMU | Yes |
| Languages | C++ and Python |
| Hardware used for reported runs | Intel Core i7-10700, 16 GB RAM, CPU only, two estimator threads |
| Throughput | 84.64 frames/s; historical aggregate native offline rate, qualification below |
| Website and source | https://github.com/sudhirpratapyadav/anchorflow-vio |
| Publication | Leave blank; the Basalt publications are credited upstream work, not an AnchorFlow publication |

Choose the permissive open-source availability category for the released
implementation, subject to the retained third-party notices. Original AnchorFlow
contributions are MIT; Basalt is BSD-3-Clause. See the dependency notices for the
separate bundled and system-library terms.

Description:

> Basalt-based monocular visual-inertial odometry using the left grayscale camera
> and right IMU. Uses fixed-template optical-flow tracking, factory IMU
> rectification and a uniform configuration across sequences. No stereo
> measurements, loop closure or offline global refinement are used. Throughput
> is historical aggregate native offline processing: 265,694 timestamps in
> 3,139.15 seconds, including observation dumping and excluding input preparation
> and evaluation. CPU-affinity conditions differed across those runs; this is
> not a controlled deployment or main-test speed benchmark.

Parameters:

> cam0 + imu0; fixed temporal templates; detection grid 50 px; outlier threshold
> 3 px; one-second initialization window; two estimator threads. Factory IMU
> rectification and a 4.2 ms IMU timestamp subtraction. The same frozen
> configs/mono.json and configs/basalt.json are used for every sequence.

## Generate an upload archive

Run every selected full sequence using [usage.md](usage.md). Collect the completed
run directories, then package them. Use `--scope test` only for actual test data.

```sh
.venv/bin/python scripts/create_manifest.py outputs/submission.json \
  outputs/sequence_1_19/run outputs/sequence_1_20/run \
  --scope training --name anchorflow-vio-training
.venv/bin/python scripts/package_submission.py outputs/submission.json outputs/package
```

For an additional check with the official parser:

```sh
.venv-eval/bin/python scripts/package_submission.py outputs/submission.json outputs/package-official --official-parser
```

Use fresh output directories. The ZIP contains only `slam/<sequence>.txt`, with
increasing integer nanosecond timestamps, translation and xyzw quaternion fields.
For this IMU method the frame is `world_from_imu`. The tools reject cropped runs,
mixed policies/runtimes, changed pinned inputs, missing timestamps, nonfinite
poses and nonunit quaternions. They never upload or certify localization quality.

## Completed test results

All 63 main-test recordings have been downloaded and processed with the frozen
monocular + IMU method. Individual estimates and all five category ZIPs plus the
combined ZIP passed official-parser, full timestamp coverage and integrity checks.
See [test_completion.md](test_completion.md) for hashes and reliability limitations.
No main-test leaderboard score is claimed before the server evaluates the upload.

Upload this single combined archive through the method's results page:

`/media/ubuntu/ext_drive/anchorflow-vio-test/packages/all_63_official/anchorflow_mono_all_63.zip`

SHA-256: `a98232b2f6a7026b6d5d9c5357bb661b162ba0401f54a340d6a5c8e04c0c0754`.

Select **Monocular** and **IMU: Yes**, and use the public GitHub source URL above.
The archive contains all five complete challenges. Uploading test results makes
the method public. Wait for server evaluation and inspect its status/results;
local format checks do not establish accuracy. The frozen results include severe
tracking discontinuities on Platform 5_4, 5_5 and 5_6, as documented in the
completion report. The owner authorized public submission on 2026-10-19;
authenticated website access is still required to perform it.

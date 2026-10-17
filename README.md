# AnchorFlow VIO

[![License: MIT](https://img.shields.io/badge/Original_code-MIT-blue.svg)](LICENSE)

Monocular visual-inertial odometry built on **Basalt**, using fixed-template
optical-flow tracking and one camera plus IMU. This repository contains the
mono-only source adaptation, frozen configuration, reproducible runner and
LaMAria submission tools.

The configuration uses LaMAria's left grayscale camera (`cam0`) and right IMU
(`imu0`). Every trajectory is initialized from those sensors alone. Stereo
images, stereo-derived depth, reference trajectories and ground truth are not
inference inputs. One configuration is used for every recording.

## Start here

1. [Build the pinned native runtime](docs/build.md).
2. [Prepare input and run a sequence](docs/usage.md).
3. [Evaluate training results](docs/evaluation.md).
4. [Create a LaMAria submission](docs/submission.md).

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
# First build the native runtime following docs/build.md.
.venv/bin/python scripts/prepare_input.py /data/sequence_1_19 outputs/sequence_1_19/input
.venv/bin/python scripts/run_sequence.py outputs/sequence_1_19/input outputs/sequence_1_19/run --runtime build/native/runtime
```

No dataset or prebuilt binary is bundled. Native source is reconstructed from a
pinned upstream Basalt commit and the historical patch used in the experiments;
build dependencies have their own licenses. The Python tools use paths relative
to this repository and accept external data/runtime paths.

## Measured training results

These are **training results, not main-test leaderboard scores**. Each category
contains two complete recordings, using the original uniform fixed-template
configuration. Official LaMAria evaluators provide CP score and pose recall.

| Category | Mean CP score | Pose recall at 5 m |
|---|---:|---:|
| Short | 74.05 | 100.00% |
| Medium | 33.68 | 70.48% |
| Long | 40.37 | 85.99% |
| Lowlight | 30.16 | 76.18% |
| Moving platform | 28.65 | Unavailable |

Ten-record mean CP: **41.38302**. All 265,694 image timestamps have output poses,
including 200 initialization fills and four later fills. Coverage is not accuracy:
**Platform12 diverges and scores zero**. Lowlight accuracy changes substantially
when initialization starts later in a recording. This is an experimental baseline,
not a robust-localization certification or a deployment-ready robot stack.

See [per-record results](benchmarks/training.csv),
[controlled-start results](benchmarks/controlled_starts.csv) and
[measurement notes](docs/results.md). Rejected feature-density, global-refinement,
Earth-rate and restart variants are not selectively mixed into this release.

Historical aggregate native processing rate is **84.64 frames/s** on an Intel
Core i7-10700 with two estimator threads. This includes observation dumping and
excludes preparation/evaluation. CPU affinity differed across historical runs;
it is not a controlled deployment-latency measurement. Main-test performance is
unmeasured.

## Configuration and checks

- [configs/mono.json](configs/mono.json): sensor, timing, IMU noise and runtime policy.
- [configs/basalt.json](configs/basalt.json): frozen native estimator configuration.
- [docs/release_validation.md](docs/release_validation.md): source-build and release checks.

```sh
.venv/bin/python -m unittest discover -s tests -v
```

## Credits and upstream projects

- **[Basalt](https://gitlab.com/VladyslavUsenko/basalt)** provides the underlying visual-inertial estimator and tracking infrastructure. Credit goes to Vladyslav Usenko, Nikolaus Demmel, and the Basalt authors and contributors. See the [project page](https://vision.in.tum.de/research/vslam/basalt), [GitHub mirror](https://github.com/VladyslavUsenko/basalt), and [BSD-3-Clause license](https://gitlab.com/VladyslavUsenko/basalt/-/blob/master/LICENSE).
- **[LaMAria](https://lamaria.ethz.ch/)** provides the benchmark recordings, calibration data, evaluation protocol, and official evaluation tools used in this project. Credit goes to the LaMAria authors and contributors. See the [evaluation source code](https://github.com/cvg/lamaria) and [dataset and submission documentation](https://lamaria.ethz.ch/slam_documentation).
- **[Project Aria](https://facebookresearch.github.io/projectaria_tools/)** provides the sensor platform and public sensor/calibration documentation underlying the LaMAria recordings.

AnchorFlow's work covers the mono input adaptation, fixed-template tracking configuration, reproducible evaluation, and submission tooling. The underlying Basalt estimator and upstream algorithms remain credited to their original authors. These acknowledgments do not imply endorsement by the upstream projects.

### Relevant Basalt publications

- V. Usenko, N. Demmel, D. Schubert, J. Stückler, and D. Cremers. [Visual-Inertial Mapping with Non-Linear Factor Recovery](https://arxiv.org/abs/1904.06504). IEEE Robotics and Automation Letters, 2020.
- N. Demmel, D. Schubert, C. Sommer, D. Cremers, and V. Usenko. [Square Root Marginalization for Sliding-Window Bundle Adjustment](https://arxiv.org/abs/2109.02182). ICCV, 2021.

This product includes software developed by the Autonomous Systems Lab and Skybotix AG.

Please acknowledge the relevant upstream work when using or building on this project. Third-party notices are preserved under `native/licenses/` and `licenses/`; see [the native dependency notices](native/NOTICE.md).

## License

Original AnchorFlow contributions are licensed under the [MIT License](LICENSE). Third-party code and dependencies retain their respective licenses and copyright notices.

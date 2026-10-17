# AnchorFlow VIO

Basalt-based monocular visual-inertial odometry with fixed-template optical-flow tracking and inertial fusion.

AnchorFlow uses one grayscale camera and an IMU. The current experimental configuration is evaluated on LaMAria using the left camera (`cam0`) and right IMU (`imu0`), with a uniform configuration across recordings. No stereo measurements enter the estimator.

## Status

This repository is being prepared for the mono-only source release. Implementation, build instructions, and dependency notices are not yet included. The stereo research project is separate.

The experimental baseline has been evaluated on ten LaMAria training challenge recordings. Low-light start sensitivity and failure on a moving-platform recording remain known limitations. No main-test result is claimed.

## Credits and upstream projects

- **[Basalt](https://gitlab.com/VladyslavUsenko/basalt)** provides the underlying visual-inertial estimator and tracking infrastructure. Credit goes to Vladyslav Usenko, Nikolaus Demmel, and the Basalt authors and contributors. See the [project page](https://vision.in.tum.de/research/vslam/basalt), [GitHub mirror](https://github.com/VladyslavUsenko/basalt), and [BSD-3-Clause license](https://gitlab.com/VladyslavUsenko/basalt/-/blob/master/LICENSE).
- **[LaMAria](https://lamaria.ethz.ch/)** provides the benchmark recordings, calibration data, evaluation protocol, and official evaluation tools used in this project. Credit goes to the LaMAria authors and contributors. See the [evaluation source code](https://github.com/cvg/lamaria) and [dataset and submission documentation](https://lamaria.ethz.ch/slam_documentation).
- **[Project Aria](https://facebookresearch.github.io/projectaria_tools/)** provides the sensor platform and public sensor/calibration documentation underlying the LaMAria recordings.

AnchorFlow's work covers the mono input adaptation, fixed-template tracking configuration, reproducible evaluation, and submission tooling. The underlying Basalt estimator and upstream algorithms remain credited to their original authors. These acknowledgments do not imply endorsement by the upstream projects.

### Relevant Basalt publications

- V. Usenko, N. Demmel, D. Schubert, J. Stückler, and D. Cremers. [Visual-Inertial Mapping with Non-Linear Factor Recovery](https://arxiv.org/abs/1904.06504). IEEE Robotics and Automation Letters, 2020.
- N. Demmel, D. Schubert, C. Sommer, D. Cremers, and V. Usenko. [Square Root Marginalization for Sliding-Window Bundle Adjustment](https://arxiv.org/abs/2109.02182). ICCV, 2021.

Please acknowledge the relevant upstream work when using or building on this project. Third-party license notices will accompany the corresponding code in the implementation release.

## License

Original AnchorFlow contributions are licensed under the [MIT License](LICENSE). Third-party code and dependencies retain their respective licenses and copyright notices.

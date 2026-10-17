# Factory IMU coefficient fixtures

These two numeric calibration fixtures reproduce the measured training policy.
They encode Project Aria right-IMU factory rectification as
`raw = M @ rectified + bias`; inference solves this affine equation.
They were recovered from factory-calibrated recordings, not fitted to SLAM
ground-truth trajectories. The `from`, `device`, model and fit-residual fields
inside each file preserve their original provenance.

File keys are the first eight hex digits of the corresponding supplied Aria
calibration JSON's MD5, matching the historical lookup. This is a device lookup,
not a security hash or a promise that other files with similar calibration are
compatible. Generated run manifests use SHA-256 for reproducibility checks.

Only the measured training calibration keys are covered. An unknown test key
requires verified factory calibration; do not silently use identity matrices,
copy another device's fixture or rename an existing file. No imagery or reference
trajectory is included here. Credit: [Project Aria calibration documentation](https://facebookresearch.github.io/projectaria_tools/)
and the [LaMAria dataset](https://lamaria.ethz.ch/).

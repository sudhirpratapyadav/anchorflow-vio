# Changelog

## Unreleased

- Fix preparation of full recordings whose IMU ends a fraction of one image
  period before the last camera frame; retain exact historical sensor samples
  and report the gap. Version 0.1.0's strict endpoint check rejected full Short19.
- Add resumable full-test downloading, CRC/hash verification and atomic readiness.
- Add a serial frozen inference queue with independent audits and automatic
  complete-category/final submission packaging.

## 0.1.0 — 2026-10-17

Initial mono-only source release of the measured F29 fixed-template baseline.

- Pinned Basalt source and historical patch, one-camera reader, and source build script.
- Portable cam0/imu0 preparation, frozen configuration, runtime auditing and pose export.
- Official evaluation wrapper and deterministic, validated LaMAria packaging.
- Ten-record training results and ten controlled-start measurements, including failures.
- MIT original contributions with preserved upstream credits and dependency notices.

Source-built 800-frame smoke poses and observations match the original runtime
byte for byte. No full-cohort rerun with the new build or main-test score is
claimed. Platform12 divergence and lowlight start sensitivity remain unresolved.

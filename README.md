# AnchorFlow VIO

Basalt-based monocular visual-inertial odometry with fixed-template optical-flow tracking and inertial fusion.

AnchorFlow uses one grayscale camera and an IMU. The current experimental configuration is evaluated on LaMAria using the left camera (`cam0`) and right IMU (`imu0`), with a uniform configuration across recordings. No stereo measurements enter the estimator.

## Status

This repository is being prepared for the mono-only source release. Implementation, build instructions, dependency notices, and licensing are not yet included. The stereo research project is separate.

The experimental baseline has been evaluated on ten LaMAria training challenge recordings. Low-light start sensitivity and failure on a moving-platform recording remain known limitations. No main-test result is claimed.

## Acknowledgment

The estimator is based on Basalt. AnchorFlow describes this project's fixed-template tracking configuration and mono evaluation work, not a claim to have invented the underlying estimator.

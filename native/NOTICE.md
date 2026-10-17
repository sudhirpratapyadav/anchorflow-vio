# Native and third-party notices

Original AnchorFlow wrapper code is covered by the repository MIT license.
Basalt-derived code, the historical modification patch, mono reader header and
calibration template retain upstream Basalt's BSD3 terms and attribution to
Vladyslav Usenko and Nikolaus Demmel. See `licenses/BASALT-BSD-3-Clause.txt`.
Upstream source and vcpkg commit pins are in `source_manifest.json`.

**This product includes software developed by the Autonomous Systems Lab and
Skybotix AG.** The bundled ethz_apriltag2 dependency has an advertising-clause
license, preserved verbatim in `licenses/ETHZ-APRILTAG2.txt`. Bundled ROS header
notices are in `licenses/BUNDLED-ROS-HEADERS.txt`; the pinned upstream source
retains all source headers and its bundled third-party files.

`dependencies.lock.json` inventories the actual installed vcpkg manifest/configure
and transitive dependency set used for validation, including split Boost packages
and build helpers. Full installed copyright notices are under
`licenses/dependencies/`. Some are configure/build-only (for example GTest and
vcpkg build helpers), not necessarily linked into the runtime. Basalt's build
also compiles bundled AprilTag and reads bundled ROS headers. The patch retains
historically present optional code to preserve scientific reproducibility;
rejected later global/physics research is not included.

The preload reader uses the host's OpenCV development package. Host shared
libraries are required separately and are not distributed as binary files by
this source repository. The runtime's dynamic dependency/OS-package inventory
is recorded in `system_dependencies.json`; applicable distro copyright notices
are preserved in `licenses/system/`. The measured closure contains140 libraries
owned by115 distro packages, with no unidentified shared libraries.
Recheck that inventory if using a different operating system or redistributing
compiled binaries; MIT does not relicense any dependency.

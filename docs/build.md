# Native build from source

The estimator is built from Basalt commit
`0f3b2b52c807f70ff4e2973ce253c73329eea7bc` plus the exact historical F29 patch
in `patches/basalt-f29.patch`. `native/source_manifest.json` records its digest,
the original research source commit and measured binary hashes. The mutable
research Basalt checkout and previously compiled estimator objects are not build
inputs. The mono reader is a small preload library; its derived header preserves
the Basalt license and matches the historical patched reader with camera count1.

Required host tools: Linux, a C++17 compiler (validation uses GCC11), CMake>=3.24,
Ninja, Git, pkg-config, tar, Python3 and system OpenCV development files discoverable
as `pkg-config opencv4`. Basalt also requires OpenGL/EGL/X11 development
libraries used by Pangolin even when visualization is disabled. Its pinned vcpkg
manifest/ports obtain Eigen, Sophus, TBB, Boost, Pangolin and other dependencies.
The validation host is Ubuntu22.04, GCC11, system OpenCV4.5.4. No CUDA is used.

## Public source acquisition and build

On Ubuntu22.04, the following is a practical prerequisite starting point. The
GL/X11 packages correspond to the runtime requirements in pinned upstream
`scripts/install.sh`, with development headers for compilation. This command
has not been tested on a clean OS image; transitive vcpkg ports may request
additional host tools. No host apt packages were installed for native validation.

```sh
sudo apt-get update
sudo apt-get install build-essential git pkg-config tar curl zip unzip \
  python3 python3-venv python3-pip ninja-build libopencv-dev \
  libegl1-mesa-dev libgl1-mesa-dev libglu1-mesa-dev libglew-dev \
  libx11-dev libxcursor-dev libxinerama-dev libxrandr-dev libxi-dev libxtst-dev
python3 -m venv build-tools
build-tools/bin/pip install 'cmake>=3.24' ninja
export PATH="$PWD/build-tools/bin:$PATH"
```

An existing system CMake>=3.24 and Ninja can replace the tool environment above.
The builder selects tools from `PATH` unless `--cmake`/`--ninja` override them.
These are user-operated network commands; they do not fetch benchmark data:

```sh
git clone https://gitlab.com/VladyslavUsenko/basalt.git upstream-basalt
git -C upstream-basalt checkout 0f3b2b52c807f70ff4e2973ce253c73329eea7bc
git -C upstream-basalt submodule update --init --recursive
upstream-basalt/thirdparty/vcpkg/bootstrap-vcpkg.sh -disableMetrics
python3 scripts/build_native.py --source-repo upstream-basalt --work build/native
```

The vcpkg submodule must be commit
`1e199d32ad53aab1defda61ce41c380302e3f95c`; the script checks it. Without
`--deps-prefix`, CMake/vcpkg installs the pinned build dependencies into the new
owned work directory. This can download and build dependencies and take substantial
time. The build script compiles `basalt_vio` with one worker (`-j1`),
`-ffp-contract=off`, the historical Release configuration and native CPU target.
It does not install into the system or copy an old Basalt binary.

Use a memory-limited worker on constrained hosts, for example:

```sh
systemd-run --user --unit=anchorflow-build --property=MemoryMax=4G \
  --property=CPUQuota=200% --property=Nice=15 --property=LimitCORE=0 \
  --working-directory="$PWD" \
  /usr/bin/timeout 10800 /usr/bin/taskset -c 14,15 \
  /usr/bin/python3 scripts/build_native.py \
  --source-repo "$PWD/upstream-basalt" --work "$PWD/build/native"
```

Choose available CPU IDs on other hosts. Do not compile large C++ units on the
robot. `--resume` reuses an interrupted owned build only after checking the
reconstructed source hashes. `--cmake` and `--ninja` select installed tool binaries.

## Offline validation and runtime interface

For an existing compatible dependency cache, supply
`--deps-prefix /path/to/vcpkg_installed` and optionally `--vcpkg /path/to/pinned/vcpkg`.
This disables manifest installation and reads that prefix without modifying it.
Our local source rebuild uses this mode; a completely network-fresh dependency
build has not yet been measured. `native/dependencies.lock.json` captures the
installed package versions/ABIs and notices from that validation cache. It is
provenance, not a claim that arbitrary cache versions reproduce the results.

The completed `WORK/runtime` directory contains:

- `basalt_vio`: freshly compiled executable;
- `libbasalt.so`: freshly compiled estimator;
- `libmono_reader.so`: freshly compiled one-camera loader;
- `manifest.json`: runtime-relative SHA256 entries and build provenance.

Pass that directory to the Python runner's `--runtime` option. The runner must
set `LD_PRELOAD` to the mono reader and `LD_LIBRARY_PATH` to this directory, and
must pass the frozen one-camera calibration/configuration. Native output must
contain `MONO_READER: exactly one camera, cam0`. No cam1 view is prepared.
The public calibration template is `native/calibration_template.json`, copied
from the pinned upstream `data/euroc_eucm_calib.json` under Basalt's BSD license;
actual sensor parameters are replaced by the input preparer.

Build paths/compiler versions can change binary hashes. Historical hashes are
recorded as evidence, not a compiler-independent bitwise guarantee. Scientific
parity requires running the same sensor input and comparing native poses before
claiming the historical benchmark measurements for a new runtime.
`native/validation.json` records the completed fresh43-target rebuild and
800-image (40-second) smoke: native trajectory and all800 observation files
were byte-identical to the frozen reference. This is not a rebuilt full-ten-record
benchmark validation.

See `native/NOTICE.md` for dependency scope and license notices. The repository's
MIT license does not replace third-party licenses.

#!/usr/bin/env python3
"""Convert the runner's TUM trajectory (seconds) into a LaMAria submission file.

Output: one line per image timestamp (nanoseconds), `ts tx ty tz qx qy qz qw`,
world_from_imu. Images without an estimate (before initialisation, or after a
dropped frame) get the nearest earlier pose carried forward; images before the
first estimate get the first pose. Fill counts are reported explicitly: a
complete trajectory can still contain inaccurate or stale poses.

Usage: tum_to_submission.py trajectory.tum image_timestamps_ns.txt out.txt
"""
import argparse
import json
import sys
from pathlib import Path

import numpy as np


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("tum", type=Path)
    ap.add_argument("image_timestamps_ns", type=Path)
    ap.add_argument("out", type=Path)
    ap.add_argument("--tolerance-ms", type=float, default=1.0)
    ap.add_argument("--skip-images", type=int, default=0,
                    help="exclude only an intentional experiment start offset; fill initialization within the remaining interval")
    ap.add_argument("--drop-before-first", action="store_true",
                    help="omit images before the first estimate (for diagnostics only; a submission must have every image)")
    args = ap.parse_args()

    rows = [l.split() for l in args.tum.read_text().splitlines() if l.strip() and not l.startswith("#")]
    if not rows:
        sys.exit("empty trajectory")
    est_ts = np.array([float(r[0]) for r in rows]) * 1e9
    est = [r[1:8] for r in rows]
    img_ts = np.array([int(l) for l in args.image_timestamps_ns.read_text().split()], dtype=np.int64)
    if args.skip_images < 0 or args.skip_images >= len(img_ts):
        sys.exit("skip-images must leave at least one image")
    img_ts = img_ts[args.skip_images:]
    values = np.array([[float(v) for v in r[:8]] for r in rows])
    if values.shape[1] != 8 or not np.isfinite(values).all() or np.any(np.diff(est_ts) <= 0):
        sys.exit("trajectory must have finite poses and strictly increasing timestamps")
    if np.any(np.diff(img_ts) <= 0):
        sys.exit("image timestamps must be strictly increasing")

    tol = args.tolerance_ms * 1e6
    idx = np.searchsorted(est_ts, img_ts)
    matched = np.full(len(img_ts), -1, dtype=np.int64)
    for k in (idx - 1, idx):
        kk = np.clip(k, 0, len(est_ts) - 1)
        ok = np.abs(est_ts[kk] - img_ts) <= tol
        matched[ok] = kk[ok]

    filled = matched.copy()
    last = int(np.argmax(matched >= 0))  # first matched index
    last = matched[last] if (matched >= 0).any() else 0
    for i in range(len(filled)):
        if filled[i] >= 0:
            last = filled[i]
        else:
            # carry forward the latest estimate that is not in the future
            j = np.searchsorted(est_ts, img_ts[i], side="right") - 1
            filled[i] = max(j, 0) if j >= 0 else last
    written = 0
    with open(args.out, "w") as f:
        for ts, j in zip(img_ts, filled):
            if args.drop_before_first and ts < est_ts[0] - tol:
                continue
            f.write(f"{ts} " + " ".join(est[j]) + "\n")
            written += 1

    n_match = int((matched >= 0).sum())
    before_first = int((img_ts < est_ts[0] - tol).sum())
    stats = {
        "images": int(len(img_ts)),
        "intentionally_skipped_images": args.skip_images,
        "output_poses": written,
        "complete_coverage": written == len(img_ts),
        "estimates": int(len(est_ts)),
        "matched_within_tolerance": n_match,
        "images_before_first_estimate": before_first,
        "gap_filled_after_init": int(len(img_ts) - n_match - before_first),
    }
    print(json.dumps(stats))


if __name__ == "__main__":
    main()

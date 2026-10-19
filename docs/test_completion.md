# Completed test submission package

All 63 test datasets and trajectories are complete on the external drive. All
63 estimates passed the official parser, full image timestamp coverage, finite
pose/unit quaternion checks, and hashes against their individual audit receipts.
All five category archives and the combined archive passed CRC and exact-member
content checks. The 22 Python tests pass. No leaderboard upload was performed.

Storage root: `/media/ubuntu/ext_drive/anchorflow-vio-test`.

| Package | Recordings | SHA-256 |
|---|---:|---|
| `category_1_official` | 18 | `a7b3f36d45bf6fa58370a9c0c3fa5848f245dd27b6cedc1231cc815559727f37` |
| `category_2_official` | 10 | `34674650d1e347cd8b8776854aa1ebacc6e61f9646b4734e256bbee8dd786dfc` |
| `category_3_official` | 16 | `134d4e8a9fa1ad37a79f0b9570584b32f49e6668a1da05927e17a368596d0721` |
| `category_4_official` | 9 | `7f105b931e32428c5ed82fb8618957b60e3045e2f47a1ed2cb5cad8535c768c4` |
| `category_5_official` | 10 | `8d3a5baadeca9b8da41ea42b93f8ad09197b619473fc02936cc278657460dd54` |
| `all_63_official` | 63 | `a98232b2f6a7026b6d5d9c5357bb661b162ba0401f54a340d6a5c8e04c0c0754` |

The combined upload archive is
`packages/all_63_official/anchorflow_mono_all_63.zip` under the storage root.
Category archives are in `packages/category_N_official/`. Per-recording native
logs, timing, input provenance, trajectories and audits are in `runs/`; individual
parser receipts and final audit summaries are in `validation/`.

## Reliability limitations

These checks establish submission format and coverage, not hidden-test accuracy.
The frozen method exhibits severe tracking discontinuities on Platform sequences
5_4, 5_5 and 5_6 (maximum consecutive steps approximately 181, 125 and 109 m).
Their original outputs are preserved and included. No configuration selection or
trajectory repair was performed using hidden-test behavior. The benchmark score
remains unknown until evaluation.

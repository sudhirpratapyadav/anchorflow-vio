# Measurement scope

The original F29 mono fixed-template configuration is the release baseline. The
ten-record full-training table is `benchmarks/training.csv`. The original
fixed/rolling comparison is `benchmarks/frontend_scores.csv`. These figures were
measured in the isolated research checkout before the portable release tooling
was extracted. Source-build parity checks are reported separately in
`release_validation.md`; a short smoke is not a new ten-record accuracy study.

## Full records

The ten recordings cover two examples each of Short, Medium, Long, Lowlight and
Moving Platform. Mean CP is 41.38302. All 265,694 requested timestamps are emitted,
including 200 initial fills and four later fills. Platform12's official CP is
zero and the native trajectory diverges. Platform11 performs substantially
better; the mean must not conceal the failure.

CPU totals: 5,362.35 CPU seconds; native wall sum: 3,139.15 seconds. Dividing image
count by wall sum gives 84.6388 frames/s. This is an aggregate offline rate with
observation dumping; it excludes preparation, evaluation and packaging. The
earliest run used different CPU-affinity conditions. Two estimator threads were
requested, and later runs were bound to two logical CPUs. Do not interpret this
as end-to-end latency, an isolated hardware comparison, or test-set throughput.

## Fresh starts

Ten additional runs start at 30 or 120 seconds on Short19, Medium12, Long17,
Lowlight10 and Platform12, then process the entire remainder. The CSV compares
each with the original trajectory restricted to the same suffix; reference
recall still includes the missing prefix. No favorable start is selected for
the release configuration, which starts at image zero.

Lowlight10 at 30 seconds falls to CP 6.14444 against its matched suffix control's
23.23509; at 120 seconds it reaches 41.99533 against 23.14418. Medium12 is also
start-sensitive. Platform12 diverges at both offsets. All native executions and
format/sensor audits passed; those checks do not establish localization accuracy.

## Rejected experiments

- Rolling templates improve Medium12 but harm the other three initial records.
- A denser feature grid improves Medium12 strongly but hurts most other records
  and catastrophically diverges on Lowlight11.
- Mono-only global reconstruction has a four-record mean CP change of -0.26689.
- The tested Earth-rate model has a four-record mean CP change of -0.31874
  versus the original frontend, with higher compute cost and a nonconverged
  selected endpoint.
- A conservative restart guard contains one runaway but leaves Platform12 at CP 0.

None passed its predeclared promotion criteria. Their changes are excluded from
the inference configuration, and there is no per-sequence winner selection.
This does not establish that all possible mono improvements have been exhausted.

## Provenance and limitations

Research mono closeout commit: `46c98a5` in the separate research checkout.
Native source provenance and frozen runtime fingerprints are recorded in
`native/source_manifest.json`. Every baseline estimate was independently rescored
with the official evaluator; the release packager also validates the official
trajectory parser when requested.

Unmeasured: main-test performance, physical robot performance, online latency,
and general robustness outside these recordings. Numerical finite-pose and
coverage checks cannot detect every tracking failure. Training data, raw images,
trajectories and internal research histories are not bundled with the source.

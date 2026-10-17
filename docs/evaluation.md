# Official evaluation environment

Training scores use the official [LaMAria evaluator](https://github.com/cvg/lamaria),
pinned to commit `aa811b3281981930f30328d3cf5fad04a331e93e`.
`scripts/evaluate.py` invokes its control-point triangulation/alignment and dense
recall routines. The additional ATE/scale fields are diagnostics; challenge CP
score and pose recall are the primary reported metrics.

The evaluation environment is separate from inference. The measured environment
used NumPy 2.2.6, SciPy 1.15.3, evo 1.31.1, pyceres 2.6,
pycolmap 3.13.0.dev0 and projectaria-tools 2.3.0. In particular, use the official
LaMAria pycolmap wheel index: an arbitrary stable pycolmap replacement need not
expose the required API.

```sh
python3 -m venv .venv-eval
.venv-eval/bin/python -m pip install -r requirements-evaluation.txt
git clone https://github.com/cvg/lamaria.git third_party/lamaria
git -C third_party/lamaria checkout aa811b3281981930f30328d3cf5fad04a331e93e
.venv-eval/bin/python -m pip install --no-deps -e third_party/lamaria
```

These commands install dependencies when run; they do not download benchmark data.
The upstream repository also provides its broader full-pipeline requirements.
The smaller requirements file here covers this release's scoring path. The
release validation receipt states which environment was actually tested.

The controlled-start CSV compares each fresh start with the original trajectory
restricted to the identical suffix. Official recall uses the complete reference
denominator, including the missing prefix. Do not compare cropped-start recall
directly with the full-record baseline or select favorable start offsets.

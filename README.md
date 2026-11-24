# Pyra in the browser

`site/` is a static single-page playground: write Pyra (`@prove` functions), press Run, and see every proof step
checked by Pyra's kernel running client-side. Nothing is sent to a server.

## How it works

* **Kernel, elaborator, Lean importer, Z3**: the same C++ sources as the native build, compiled to WebAssembly with
  Emscripten 3.1.58 as a Pyodide 0.27.8 (CPython 3.12) extension module (`wasm/build.sh`).
* **Python frontend**: the unmodified `pyra` package, run by Pyodide inside a Web Worker (`site/worker.js`),
  driven by `web/py/pyra_web.py`.
* **Library**: the bundled Lean 4 core + Mathlib export (33,128 declarations) is admitted with the verified-import
  marker from a full native re-check of the same content hash; the page can also re-check it in the browser.
  Mathlib modules that native Pyra imports from `.olean` files on demand (sqrt, log, exp, real powers, trigonometry,
  rationals, divisors) ship as a supplement (`wasm/make_supplement.py`), loaded the first time a proof needs it.

## Build

Needs a Pyra checkout on branch `web-ide` (it carries the `#ifdef __EMSCRIPTEN__` changes and the `ideal_reduce`
fix listed below), built natively, with `third_party/emsdk` (Emscripten 3.1.58):

```bash
export PYRA_ROOT=/path/to/PYRA          # Pyra checkout, `make build` done there
wasm/build_deps.sh                  # GMP + Z3 for wasm32 (once; needs third_party/emsdk 3.1.58)
wasm/build.sh                       # pyra_bind for Pyodide
python wasm/make_supplement.py      # optional: Mathlib supplement (needs Lean + Mathlib + lean4export)
python wasm/make_wheel.py           # -> site/pyra-*.whl (+ pyra_supplement.ndjson.gz)
python -m http.server -d web/site       # serve; any static host works (no special headers needed)
```

Tests (`wasm/node/`, `npm install` there): `node test.mjs` (smoke test under Node), `node corpus.mjs proofs.json`
(re-verify a corpus), `node one.mjs proofs.json NAME` (one proof, isolated), `node browser_test.mjs URL` (headless
Chrome end to end).

## What differs from native Pyra

| | native | browser |
|---|---|---|
| threads | per-step proof search races a background counterexample query | no threads: steps run synchronously |
| counterexamples | Z3 Python bindings | not available (Pyodide has no `z3` package); the C++ Z3 stage works |
| stack | proofs run on a 1 GB stack | 256 MB C stack, but the browser's JavaScript engine caps WebAssembly recursion at about 1 MB |
| Mathlib | any module, from `.olean` files | bundle + supplement only |
| speed | 1x | about 2-3x slower; the per-step timeout is 30 s instead of 10 s |

On the 65 miniF2F-valid proofs that Opus wrote and Pyra accepted natively (condition C4s), the browser build
verifies 63 at the browser's default stack size; the other 2 exceed the browser's recursion limit (the page reports
this and restarts its runtime).

## Changes to the C++ sources

All behind `#ifdef __EMSCRIPTEN__` except the `ideal_reduce` fix: inline (thread-free) paths for the two thread
pools, a heap-allocated big stack for `run_big_stack`, and `run_on_big_stack` for the browser runtime. The native
module is byte-identical to before these changes.

`src/pyra_elab/real_arith.cpp` `ideal_reduce`: fixed a use-after-free (the loop incremented an iterator into a map it
had just replaced). Natively the freed memory still held the old values, so results were unaffected; under
WebAssembly's allocator it crashed. Same reduction order, now well defined.

Linking note: the module is linked with `-Wl,-Bsymbolic`. Without it, Pyodide's loader resolved some C++ template
instantiations shared by Pyra and Z3 to the wrong functions, so Z3's tactics called into unrelated code.

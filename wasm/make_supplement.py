"""Build the browser library supplement: Mathlib modules that native Pyra imports from .olean files on demand.

    python wasm/make_supplement.py      # -> wasm/build/supplement/{pyra_supplement.ndjson.gz, supplement.json}

Natively, `sqrt`, `log`, `logb`, `exp` (pyra.finset.require_for) and `pyra.require(modules=[...])` read Mathlib's
.olean files, which a browser does not have.  This exports the same declarations (the public declarations of
SUPPLEMENT_MODULES plus their dependency closure, as `pyra.require(modules=...)` loads them) with lean4export, then
re-checks the export in Pyra's kernel on top of the bundle and records its content hash and the instance list that
`pyra.require` would install, so the browser runtime can load it with the verified-import marker.
"""
from __future__ import annotations

import gzip
import importlib
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

WEB = Path(__file__).resolve().parents[1]
ROOT = Path(os.environ["PYRA_ROOT"]).resolve()  # a Pyra checkout (branch web-ide)
OUT = WEB / "wasm" / "build" / "supplement"
SUPPLEMENT_MODULES = [
    "Mathlib.Analysis.Real.Sqrt", "Mathlib.Analysis.SpecialFunctions.Log.Basic",
    "Mathlib.Analysis.SpecialFunctions.Log.Base", "Mathlib.Analysis.SpecialFunctions.Exp",
    "Mathlib.Analysis.SpecialFunctions.Pow.Real", "Mathlib.Analysis.SpecialFunctions.Trigonometric.Basic",
    "Mathlib.Data.Rat.Lemmas", "Mathlib.NumberTheory.Divisors",
]
ELAN = ROOT / "third_party" / "elan"
MATHLIB = ROOT / "third_party" / "mathlib"
EXPORTER = ROOT / "third_party" / "lean4export" / ".lake" / "build" / "bin" / "lean4export"


def lean_path() -> str:
    lp = [str(p / ".lake" / "build" / "lib" / "lean") for p in sorted((MATHLIB / ".lake" / "packages").iterdir())]
    return ":".join(lp + [str(ROOT / "lean" / "build")])


def main():
    sys.path.insert(0, str(ROOT))
    K = importlib.import_module("pyra.kernel")
    K.kernel()
    L = importlib.import_module("pyra.library")
    from pyra import lean_bridge
    roots = set()
    for m in SUPPLEMENT_MODULES:
        # skip notation/parser declarations (e.g. `Real.term√_`): syntax, not mathematics, and lean4export cannot parse them
        roots.update(r for r in L.module_roots(m) if not r.split(".")[-1].startswith("term"))
    # the native state after these imports: pyra.require installs every indexed instance; only those present in
    # the kernel can ever be used, so record exactly those
    L.require(modules=SUPPLEMENT_MODULES)
    k0 = K.kernel()
    instances = [(n, p) for n, p in lean_bridge.instances_from_olean(L.olean_index()) if k0.has(n)]
    print(f"{len(roots)} roots from {len(SUPPLEMENT_MODULES)} modules, {len(instances)} instances in the kernel")

    OUT.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ, ELAN_HOME=str(ELAN), PATH=f"{ELAN / 'bin'}:{os.environ['PATH']}", LEAN_PATH=lean_path())
    with tempfile.TemporaryDirectory() as d:
        src = Path(d) / "PyraWebSupplement.lean"
        src.write_text("import Pyra.Prelude\n" + "".join(f"import {m}\n" for m in SUPPLEMENT_MODULES))
        olean = ROOT / "lean" / "build" / "PyraWebSupplement.olean"
        subprocess.run(["lean", "-o", str(olean), str(src)], env=env, check=True, cwd=d)
        nd = OUT / "pyra_supplement.ndjson"
        with open(nd, "w") as out:
            subprocess.run(["bash", "-c", f'ulimit -s unlimited; exec "{EXPORTER}" PyraWebSupplement -- "$@"', "_",
                            *sorted(roots)], env=env, check=True, stdout=out, cwd=d)
        olean.unlink(missing_ok=True)
    data = nd.read_bytes()
    gz = OUT / "pyra_supplement.ndjson.gz"
    gz.write_bytes(gzip.compress(data, 9))
    nd.unlink()

    # Re-check the supplement in a fresh kernel on top of the bundle (no cache) and record its content hash.
    k = importlib.import_module("pyra.pyra_bind").Kernel()
    base = k.load_ndjson(str(K.BUNDLE), "")
    st = k.load_ndjson(str(gz), "")
    if base["failed"] or st["failed"]:
        sys.exit(f"supplement failed to check: {st['errors'][:3]}")
    meta = {"modules": SUPPLEMENT_MODULES, "content_hash": st["content_hash"], "declarations": st["declarations"],
            "checked": st["checked"], "skipped": st.get("skipped"), "instances": instances}
    (OUT / "supplement.json").write_text(json.dumps(meta))
    print(f"{gz} {gz.stat().st_size / 1e6:.1f} MB: {st['declarations']} declarations, {st['checked']} checked, "
          f"{st.get('skipped')} already in the bundle, hash {st['content_hash']}")


if __name__ == "__main__":
    main()

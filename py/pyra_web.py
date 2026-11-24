"""Browser runtime for Pyra (Pyodide, single-threaded WebAssembly).

The C++ kernel, elaborator and Lean importer are the same sources as the native build, compiled to wasm32.
Differences from the native runtime, all forced by the browser:

* No threads: ``threading.Thread`` runs its target synchronously, so a step's proof search runs to completion
  (its per-step timeout still applies) instead of being raced against a background counterexample query.
* No Z3 Python bindings in Pyodide: counterexample search is unavailable (the C++ elaborator's own Z3 stage,
  used by ``mode="sketch"``, is compiled in and works).
* Loading the library: by default the bundle is admitted with the verified-import marker produced when the same
  bundle (same content hash) was fully re-checked natively; ``load(full_check=True)`` re-checks all of it here.
"""
from __future__ import annotations

import importlib.util
import json
import os
import sys
import threading
import time
import traceback

BUNDLE_HASH = "@BUNDLE_HASH@"          # filled in by wasm/make_wheel.py
HOME = os.environ.get("PYRA_WEB_HOME", os.path.expanduser("~"))       # /home/pyodide in Pyodide
CACHE_DIR = os.path.join(HOME, ".cache", "pyra", "verified")


class _SyncThread:
    """Stand-in for threading.Thread in a runtime without threads: start() runs the target to completion."""

    def __init__(self, group=None, target=None, name=None, args=(), kwargs=None, *, daemon=None):
        self._target, self._args, self._kwargs = target, args, kwargs or {}
        self.name, self.daemon, self._started = name, daemon, False

    def start(self):
        self._started = True
        if self._target:
            self._target(*self._args, **self._kwargs)

    def join(self, timeout=None):
        return None

    def is_alive(self):
        return False


threading.Thread = _SyncThread
_state = {"loaded": False, "stats": None, "runs": 0}


def _without_z3_python():
    """Pyodide has no `z3` Python package: the Python-side SMT helpers (counterexample search and the
    sketch-mode validity re-check) report "nothing found" instead of failing the step with an ImportError."""
    try:
        import z3  # noqa: F401
        return
    except ImportError:
        pass
    from pyra import counterexample as cex
    cex.smt_valid = lambda *a, **k: False

    def start(self):
        self.fired_at = time.perf_counter()
        self.result = None
        self.done.set()
        return self

    cex.Engine.start = start


SUPPLEMENT = {"url": "pyra_supplement.ndjson.gz", "loaded": False, "meta": None}


def _fetch(url: str) -> bytes:
    """Synchronous binary download from a Web Worker (or a local path, for tests under Node)."""
    if os.path.exists(url):
        with open(url, "rb") as f:
            return f.read()
    import js  # noqa: PLC0415 -- Pyodide only
    xhr = js.XMLHttpRequest.new()
    xhr.open("GET", url, False)
    xhr.responseType = "arraybuffer"
    xhr.send(None)
    if xhr.status != 200:
        raise RuntimeError(f"could not download {url} (HTTP {xhr.status})")
    return bytes(js.Uint8Array.new(xhr.response).to_py())


def _load_supplement():
    """Mathlib modules that native Pyra imports from .olean files on demand (sqrt, log, exp, rpow, trig, ...):
    exported with lean4export (wasm/make_supplement.py) and admitted with the verified-import marker of the
    same content (fully re-checked natively on top of the bundle)."""
    if SUPPLEMENT["loaded"]:
        return
    from pyra.kernel import kernel, elab
    meta = SUPPLEMENT["meta"]
    path = os.path.join(HOME, "pyra_supplement.ndjson.gz")
    data = _fetch(os.environ.get("PYRA_WEB_SUPPLEMENT", SUPPLEMENT["url"]))
    with open(path, "wb") as f:
        f.write(data)
    if not os.environ.get("PYRA_NO_CACHE"):
        with open(os.path.join(CACHE_DIR, meta["content_hash"] + ".verified"), "w") as f:
            f.write("pyra verified import (native full re-check of the same supplement)\n")
    st = kernel().load_ndjson(path, "" if os.environ.get("PYRA_NO_CACHE") else CACHE_DIR)
    if st["failed"] or st["content_hash"] != meta["content_hash"]:
        raise RuntimeError(f"library supplement failed to load: {st['errors'][:3] or 'content hash mismatch'} "
                           f"({len(data)} bytes downloaded, starting {data[:4]!r}; got {st['content_hash']}, "
                           f"expected {meta['content_hash']})")
    elab().set_instances([tuple(x) for x in meta["instances"]])
    elab().reindex()
    SUPPLEMENT["loaded"] = True
    SUPPLEMENT["stats"] = {k: st.get(k) for k in ("declarations", "checked", "trusted", "skipped")}


def _browser_require(*names, modules=(), search=(), threads=0):
    """pyra.require without .olean files: bundled modules are already loaded, the supplement's modules are loaded
    from the supplement; anything else is reported as unavailable in the browser build."""
    from pyra import library, lean_bridge
    from pyra.kernel import kernel
    meta = SUPPLEMENT["meta"] or {"modules": []}
    available = set(lean_bridge.bundled_modules()) | set(meta["modules"])
    k = kernel()
    if (set(modules) | set(search)) & set(meta["modules"]) or any(not k.has(n) for n in names):
        if meta["modules"]:
            _load_supplement()
    missing_mods = [m for m in list(modules) + list(search) if m not in available]
    missing = [n for n in names if not k.has(n)]
    if missing_mods or missing:
        raise lean_bridge.LeanSetupError(
            "not available in the browser build: " + ", ".join(missing_mods + missing)
            + ". The browser library holds the bundled Lean core + Mathlib subset and the modules "
            + ", ".join(m.replace("Mathlib.", "") for m in meta["modules"]) + "; natively Pyra imports any Mathlib "
            "module from Lean's .olean files.")
    library._loaded_modules.update(modules)
    return {"declarations": 0}


def _install_browser_require():
    import pyra
    from pyra import library
    meta_path = os.path.join(os.path.dirname(library.__file__), "data", "supplement.json")
    if os.path.exists(meta_path):
        with open(meta_path) as f:
            SUPPLEMENT["meta"] = json.load(f)
    pyra.require = library.require = _browser_require


def load(full_check: bool = False) -> str:
    """Import the bundled Lean core + Mathlib library into the kernel. Returns JSON load statistics."""
    if _state["loaded"]:
        return json.dumps(_state["stats"])
    os.makedirs(CACHE_DIR, exist_ok=True)
    os.environ["PYRA_CACHE_DIR"] = CACHE_DIR
    if full_check:
        os.environ["PYRA_NO_CACHE"] = "1"
    else:
        with open(os.path.join(CACHE_DIR, BUNDLE_HASH + ".verified"), "w") as f:
            f.write("pyra verified import (native full re-check of the same bundle)\n")
    t0 = time.time()
    import pyra  # noqa: F401
    _without_z3_python()
    if sys.platform == "emscripten" or os.environ.get("PYRA_WEB_BROWSER_REQUIRE"):
        _install_browser_require()           # WebAssembly build: no .olean files
    K = importlib.import_module("pyra.kernel")
    K.kernel()
    s = dict(K._load_stats or {})
    stats = {k: s.get(k) for k in ("declarations", "checked", "trusted", "failed", "content_hash", "cache_hit")}
    stats["seconds"] = round(time.time() - t0, 2)
    stats["mode"] = "full re-check in the browser" if full_check else "verified-import marker (same content hash)"
    _state.update(loaded=True, stats=stats)
    return json.dumps(stats)


def _step(s) -> dict:
    return {"line": s.line, "kind": s.kind, "source": s.source, "text": s.text, "badge": s.badge, "stage": s.stage,
            "lemmas": list(s.lemmas or []), "ms": round(s.ms, 1), "detail": s.detail, "counterexample": s.counterexample}


class _NotProved:
    """Stands in for a theorem that was not proved, so a later proof that uses it gets a clear message."""

    def __init__(self, name):
        self.__name__ = name

    def __call__(self, *args, **kwargs):
        raise RuntimeError(f"theorem {self.__name__!r} was not proved above, so it cannot be used as a lemma here")


def run(source: str, mode: str = "strict", timeout: float = 30.0) -> str:
    """Run a Pyra file. Every @prove theorem is checked; returns JSON with per-theorem, per-step results.

    `timeout` is per proof step (native default 10 s; WebAssembly runs the same search 2-3x slower)."""
    import pyra
    import pyra.ast as past
    load()
    _state["runs"] += 1
    name = f"pyra_user_{_state['runs']}"
    path = os.path.join(HOME, f"{name}.py")
    with open(path, "w") as f:
        f.write(source)
    theorems = []
    orig = past.prove

    def recording(fn=None, **kw):
        """@prove that records each theorem's outcome instead of stopping the file at the first failure."""
        kw.setdefault("mode", mode)
        kw.setdefault("timeout", timeout)

        def deco(f):
            t0 = time.time()
            entry = {"name": f.__name__, "line": f.__code__.co_firstlineno, "mode": kw["mode"]}
            try:
                thm = orig(f, **kw)
                entry.update(ok=True, verified=bool(thm.verified), statement=thm.text, report=thm.report(),
                             steps=[_step(s) for s in thm.steps])
                result = thm
            except pyra.ProofError as e:
                entry.update(ok=False, verified=False, error=str(e), report=e.report or "",
                             steps=[_step(s) for s in e.steps])
                result = _NotProved(f.__name__)
            except Exception as e:  # elaboration errors: bad statement, unknown name, unsupported construct
                msg = f"{type(e).__name__}: {e}"
                if "olean files not found" in msg:
                    msg = (f"{f.__name__}: this proof uses Mathlib declarations outside the library bundled with the "
                           "browser build (natively Pyra loads them from Lean's .olean files, which are not available here).")
                entry.update(ok=False, verified=False, error=msg, report="", steps=[])
                result = _NotProved(f.__name__)
            entry["seconds"] = round(time.time() - t0, 2)
            theorems.append(entry)
            return result

        return deco(fn) if fn is not None else deco

    out = {"theorems": theorems, "error": ""}
    pyra.prove = past.prove = recording
    t0 = time.time()
    try:
        spec = importlib.util.spec_from_file_location(name, path)
        mod = importlib.util.module_from_spec(spec)
        sys.modules[name] = mod
        big = getattr(importlib.import_module("pyra.pyra_bind"), "run_on_big_stack", None)
        (big or (lambda f: f()))(lambda: spec.loader.exec_module(mod))     # the whole file on the 256 MB stack
    except BaseException as e:  # noqa: BLE001 -- report anything the file raises outside a theorem
        tb = traceback.format_exc().strip().splitlines()
        out["error"] = "\n".join(l for l in tb[-8:] if "pyra_web.py" not in l)
        if "olean files not found" in out["error"]:
            out["error"] = ("This file loads Mathlib modules (pyra.require / Mathlib names) outside the library bundled with the "
                            "browser build. Natively Pyra imports them from Lean's .olean files, which are not available here.")
    finally:
        pyra.prove = past.prove = orig
        sys.modules.pop(name, None)
    out["seconds"] = round(time.time() - t0, 2)
    return json.dumps(out)

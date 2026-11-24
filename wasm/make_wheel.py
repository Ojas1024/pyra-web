"""Package Pyra for Pyodide 0.27 (cp312, wasm32) as a wheel the web page loads with pyodide.loadPackage().

    python wasm/make_wheel.py        # -> site/pyra-<version>-cp312-cp312-pyodide_2024_0_wasm32.whl

Contents: the pure-Python `pyra` package and its data (bundled Lean core + Mathlib export), the WebAssembly build of
`pyra_bind` (wasm/build.sh), and the browser bootstrap `pyra_web` with the bundle's content hash filled in.
"""
from __future__ import annotations

import base64
import hashlib
import importlib
import io
import sys
import zipfile
from pathlib import Path

import os
WEB = Path(__file__).resolve().parents[1]
ROOT = Path(os.environ["PYRA_ROOT"]).resolve()  # a Pyra checkout (branch web-ide)
SO = WEB / "wasm" / "build" / "pyra_bind.cpython-312-wasm32-emscripten.so"
OUT = WEB / "site"
VERSION = "0.5.2"
TAG = "cp312-cp312-pyodide_2024_0_wasm32"
SKIP = ("__pycache__", ".ipynb_checkpoints")


def bundle_hash() -> str:
    """The content hash the kernel computes for the bundle (the verified-import marker's name)."""
    sys.path.insert(0, str(ROOT))
    K = importlib.import_module("pyra.kernel")
    K.kernel()
    return K._load_stats["content_hash"]


def main():
    if not SO.exists():
        sys.exit(f"missing {SO}: run wasm/build.sh first")
    OUT.mkdir(parents=True, exist_ok=True)
    files: dict[str, bytes] = {}
    for p in sorted((ROOT / "pyra").rglob("*")):
        rel = p.relative_to(ROOT)
        if p.is_dir() or any(s in rel.parts for s in SKIP) or p.suffix == ".so" or p.suffix == ".pyc":
            continue
        files[str(rel)] = p.read_bytes()
    files[f"pyra/{SO.name}"] = SO.read_bytes()
    supp = WEB / "wasm" / "build" / "supplement"
    if (supp / "supplement.json").exists():          # wasm/make_supplement.py: served next to the page, loaded lazily
        files["pyra/data/supplement.json"] = (supp / "supplement.json").read_bytes()
        (OUT / "pyra_supplement.ndjson.gz").write_bytes((supp / "pyra_supplement.ndjson.gz").read_bytes())
    boot = (WEB / "py" / "pyra_web.py").read_text().replace("@BUNDLE_HASH@", bundle_hash())
    files["pyra_web.py"] = boot.encode()
    dist = f"pyra-{VERSION}.dist-info"
    files[f"{dist}/METADATA"] = f"Metadata-Version: 2.1\nName: pyra\nVersion: {VERSION}\nSummary: Pyra proof language (WebAssembly build)\n".encode()
    files[f"{dist}/WHEEL"] = f"Wheel-Version: 1.0\nGenerator: pyra-make-wheel\nRoot-Is-Purelib: false\nTag: {TAG}\n".encode()
    files[f"{dist}/top_level.txt"] = b"pyra\npyra_web\n"
    record = []
    for name, data in files.items():
        digest = base64.urlsafe_b64encode(hashlib.sha256(data).digest()).rstrip(b"=").decode()
        record.append(f"{name},sha256={digest},{len(data)}")
    record.append(f"{dist}/RECORD,,")
    files[f"{dist}/RECORD"] = ("\n".join(record) + "\n").encode()
    whl = OUT / f"pyra-{VERSION}-{TAG}.whl"
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for name, data in files.items():
            # the bundle is already gzip-compressed: store it as is
            z.writestr(zipfile.ZipInfo(name, (2025, 1, 1, 0, 0, 0)), data,
                       compress_type=zipfile.ZIP_STORED if name.endswith(".gz") else zipfile.ZIP_DEFLATED)
    whl.write_bytes(buf.getvalue())
    print(f"{whl}  {whl.stat().st_size / 1e6:.1f} MB, {len(files)} files")


if __name__ == "__main__":
    main()

#!/bin/bash
# Build the Pyra kernel + elaborator + Lean importer + nanobind module as a Pyodide (0.27, Python 3.12, wasm32) extension:
#   wasm/build/pyra_bind.cpython-312-wasm32-emscripten.so
# Needs: third_party/emsdk (3.1.58), third_party/pyodide-xbuildenv (0.27.8), third_party/wasm-deps/prefix (GMP, Z3).
set -euo pipefail
WEB=$(cd "$(dirname "$0")/.." && pwd)
ROOT=$(cd "${PYRA_ROOT:?set PYRA_ROOT to a Pyra checkout (branch web-ide)}" && pwd)
source "$ROOT/third_party/emsdk/emsdk_env.sh" >/dev/null 2>&1
DEPS=$ROOT/third_party/wasm-deps/prefix
PYINC=$ROOT/third_party/pyodide-xbuildenv/0.27.8/xbuildenv/pyodide-root/cpython/installs/python-3.12.7/include/python3.12
NB=$("$ROOT/.toolchain/bin/python" -c "import nanobind,os;print(os.path.dirname(nanobind.__file__))")
OUT=$WEB/wasm/build; mkdir -p "$OUT/obj"
CXXFLAGS="-std=c++20 -O2 -fPIC -fexceptions -DNDEBUG -Dthread_local= -Wno-keyword-macro -sUSE_ZLIB=1 -I$DEPS/include -I$PYINC -I$NB/include -I$NB/ext/robin_map/include -Wno-unused-parameter"
SRCS=$(ls "$ROOT"/src/pyra_core/*.cpp "$ROOT"/src/pyra_lean_bridge/*.cpp "$ROOT"/src/pyra_elab/*.cpp "$ROOT"/src/pyra_bind/*.cpp) 
SRCS="$SRCS $NB/src/nb_combined.cpp"
export CXXFLAGS OUT
compile() { o="$OUT/obj/$(echo "$1" | sed 's|/|_|g').o"; [ "$o" -nt "$1" ] || em++ $CXXFLAGS -c "$1" -o "$o"; echo "$o"; }
export -f compile
OBJS=$(echo $SRCS | tr ' ' '\n' | xargs -P 32 -I{} bash -c 'compile {}')
em++ -O2 -Wl,-Bsymbolic ${LINK_EXTRA:-} -fexceptions -sSIDE_MODULE=2 -sEXPORTED_FUNCTIONS=_PyInit_pyra_bind -sWASM_BIGINT -sUSE_ZLIB=1 $OBJS "$DEPS/lib/libz3.a" "$DEPS/lib/libgmpxx.a" "$DEPS/lib/libgmp.a" \
     -o "$OUT/pyra_bind.cpython-312-wasm32-emscripten.so"
ls -la "$OUT"/*.so

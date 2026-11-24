#!/bin/bash
# Build GMP (+gmpxx) and Z3 as static, -fPIC, single-threaded wasm32 libraries for a Pyodide side module.
set -e
ROOT="$(cd "${PYRA_ROOT:?set PYRA_ROOT to a Pyra checkout}" && pwd)"; export PATH="$ROOT/.toolchain/bin:$PATH"
mkdir -p "$ROOT/third_party/wasm-deps"; cd "$ROOT/third_party/wasm-deps"
source ../emsdk/emsdk_env.sh >/dev/null 2>&1
PREFIX=$PWD/prefix; mkdir -p $PREFIX
FLAGS="-O2 -fPIC -fexceptions -Dthread_local= -Wno-keyword-macro"
build_gmp() {
  [ -f $PREFIX/lib/libgmpxx.a ] && return
  [ -d gmp-6.3.0 ] || (curl -sL https://ftp.gnu.org/gnu/gmp/gmp-6.3.0.tar.xz | tar xJ)
  cd gmp-6.3.0
  CC_FOR_BUILD=gcc emconfigure ./configure --host=none --disable-assembly --enable-cxx --disable-shared --enable-static \
     --prefix=$PREFIX CFLAGS="$FLAGS" CXXFLAGS="$FLAGS" > ../gmp-configure.log 2>&1
  emmake make -j32 > ../gmp-make.log 2>&1 && emmake make install >> ../gmp-make.log 2>&1
  cd ..; echo "GMP done"
}
build_z3() {
  [ -f $PREFIX/lib/libz3.a ] && return
  [ -d z3 ] || git clone -q --depth 1 --branch z3-5.4.1 https://github.com/Z3Prover/z3.git
  mkdir -p z3/build-wasm && cd z3/build-wasm
  emcmake cmake .. -DCMAKE_BUILD_TYPE=Release -DZ3_BUILD_LIBZ3_SHARED=OFF -DZ3_SINGLE_THREADED=ON -DZ3_POLLING_TIMER=ON \
     -DZ3_BUILD_EXECUTABLE=OFF -DZ3_BUILD_TEST_EXECUTABLES=OFF -DZ3_ENABLE_EXAMPLE_TARGETS=OFF -DZ3_BUILD_PYTHON_BINDINGS=OFF \
     -DCMAKE_INSTALL_PREFIX=$PREFIX -DCMAKE_C_FLAGS="$FLAGS" -DCMAKE_CXX_FLAGS="$FLAGS" -DCMAKE_POSITION_INDEPENDENT_CODE=ON \
     > ../../z3-configure.log 2>&1
  emmake make -j32 > ../../z3-make.log 2>&1 && emmake make install >> ../../z3-make.log 2>&1
  cd ../..; echo "Z3 done"
}
case "${1:-all}" in gmp) build_gmp;; z3) build_z3;; *) build_gmp & build_z3 & wait;; esac
ls $PREFIX/lib

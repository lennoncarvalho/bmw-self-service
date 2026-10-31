#!/usr/bin/env bash
#
# Build the job interpreter shared library (D-61): the vendored ediabasx
# C11 sources plus native/edx_shim.c, with plain cc and zero warnings.
#
#   scripts/build_native.sh      -> native/build/libedx.dylib (macOS) or libedx.so
#
# On macOS the library is universal (arm64 + x86_64) when the toolchain can
# target both; otherwise it is built for the host architecture only.

set -euo pipefail

cd "$(dirname "$0")/.." || exit 1

CC=${CC:-cc}
CFLAGS=(-std=c11 -O2 -Wall -Wextra -Werror -fPIC -fvisibility=default
    -Inative -Inative/ediabasx/include -Inative/ediabasx/src)
SOURCES=(native/edx_shim.c native/ediabasx/platform/posix/loaders.c native/ediabasx/src/*.c)
OUT_DIR=native/build
mkdir -p "$OUT_DIR"

case "$(uname -s)" in
    Darwin)
        OUT="$OUT_DIR/libedx.dylib"
        ARCHS=(-arch arm64 -arch x86_64)
        PROBE=$(mktemp -d)
        echo 'int main(void){return 0;}' >"$PROBE/probe.c"
        if ! "$CC" "${ARCHS[@]}" -o "$PROBE/probe" "$PROBE/probe.c" 2>/dev/null; then
            ARCHS=()
        fi
        rm -rf "$PROBE"
        "$CC" "${CFLAGS[@]}" ${ARCHS[@]+"${ARCHS[@]}"} -dynamiclib \
            -install_name @rpath/libedx.dylib -o "$OUT" "${SOURCES[@]}"
        ;;
    *)
        OUT="$OUT_DIR/libedx.so"
        "$CC" "${CFLAGS[@]}" -shared -o "$OUT" "${SOURCES[@]}"
        ;;
esac

echo "built $OUT"

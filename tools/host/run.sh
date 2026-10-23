#!/bin/sh
# Builds the Mac harness for one watch and renders a script of events to
# frames, then a contact sheet and a GIF (see harness.c for the events).
#
#   tools/host/run.sh <platform> <out_dir> <HH:MM> [events...]
#
# e.g. tools/host/run.sh gabbro /tmp/sk 10:08 s p w3000
set -e
cd "$(dirname "$0")/../.."
PLAT="$1"; OUT="$2"; shift 2
case "$PLAT" in
  gabbro)  DEFS="-DPBL_PLATFORM_GABBRO -DPBL_ROUND -DPBL_COLOR" ;;
  chalk)   DEFS="-DPBL_PLATFORM_CHALK -DPBL_ROUND -DPBL_COLOR" ;;
  *) echo "unknown platform $PLAT (chalk or gabbro)"; exit 2 ;;
esac
BIN="${TMPDIR:-/tmp}/skeleton-harness-$PLAT"
cc -O2 -Wall -Wextra -Wno-unused-parameter -Wno-unused-result $DEFS -DPLAT="\"$PLAT\"" \
  -Itools/host -Isrc/c tools/host/harness.c src/c/gfx.c src/c/movement.c src/c/palette.c -lm -o "$BIN"
mkdir -p "$OUT"
find "$OUT" -name 'f*.ppm' -delete
"$BIN" "$OUT" "$@"
# KEEP=1 leaves the raw PPM frames for tools/store_assets.py.
[ -n "$KEEP" ] || python3 tools/host/frames.py "$OUT" "${EVERY:-4}"

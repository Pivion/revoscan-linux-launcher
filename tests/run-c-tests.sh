#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
OUT="${TMPDIR:-/tmp}/revoscan-gpu-map-test-$$"
trap 'rm -f "$OUT"' EXIT
cc -std=c11 -Wall -Wextra -Werror \
  -I"$ROOT/vendor/Vulkan-Headers/include" \
  -I"$ROOT/src/vulkan_layer" \
  "$ROOT/tests/test_gpu_property_map.c" \
  "$ROOT/src/vulkan_layer/gpu_property_map.c" \
  "$ROOT/src/vulkan_layer/gpu_map_config.c" \
  -o "$OUT"
"$OUT"
printf '%s\n' 'GPU property mapping tests passed.'

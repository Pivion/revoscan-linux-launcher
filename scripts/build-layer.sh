#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
OUT="${1:-$ROOT/build/AppDir/usr/share/vulkan/explicit_layer.d/librevoscan_gpu_map.so}"
mkdir -p "$(dirname -- "$OUT")"
"${CC:-cc}" -std=c11 -fPIC -shared -Wall -Werror \
  -Wl,-soname,librevoscan_gpu_map.so \
  -I"$ROOT/vendor/Vulkan-Headers/include" \
  -I"$ROOT/src/vulkan_layer" \
  "$ROOT/src/vulkan_layer/layer.c" \
  "$ROOT/src/vulkan_layer/gpu_property_map.c" \
  "$ROOT/src/vulkan_layer/gpu_map_config.c" \
  -o "$OUT"
printf 'Built Vulkan layer: %s\n' "$OUT"

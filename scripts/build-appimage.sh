#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
IMAGE="localhost/revoscan-linux-launcher-builder:jammy"

podman build -f "$ROOT/packaging/Containerfile.ubuntu22" -t "$IMAGE" "$ROOT"
podman run --rm --user 0 -v "$ROOT:/src:Z" -w /src "$IMAGE" \
    bash /src/scripts/build-appimage-in-container.sh

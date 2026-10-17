#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
APPDIR="$ROOT/build/AppDir"
VENV="$ROOT/build/python-builder"
APPIMAGE_TOOL="$ROOT/tools/cache/appimagetool-x86_64.AppImage"
OUT="$ROOT/dist/RevoScan-Linux-Launcher-0.1.2-x86_64.AppImage"

if [[ ! -d /opt/wine-staging ]]; then
    printf 'This builder requires WineHQ Staging staged at /opt/wine-staging.\n' >&2
    exit 2
fi
if [[ "$(getconf GNU_LIBC_VERSION)" != "glibc 2.35"* ]]; then
    printf 'Expected the pinned Ubuntu 22.04 / glibc 2.35 build container; got %s.\n' "$(getconf GNU_LIBC_VERSION)" >&2
    exit 2
fi

mkdir -p "$ROOT/build" "$ROOT/dist" "$ROOT/tools/cache"
rm -rf "$APPDIR" "$ROOT/build/pyinstaller-dist" "$ROOT/build/pyinstaller-work" "$ROOT/build/pyinstaller-spec"
python3 -m venv "$VENV"
"$VENV/bin/python" -m pip install --disable-pip-version-check -r "$ROOT/requirements-build.txt"
"$VENV/bin/python" -m PyInstaller \
    --clean --noconfirm --onefile --windowed \
    --name revoscan-launcher \
    --distpath "$ROOT/build/pyinstaller-dist" \
    --workpath "$ROOT/build/pyinstaller-work" \
    --specpath "$ROOT/build/pyinstaller-spec" \
    --paths "$ROOT/src" \
    --collect-data certifi \
    "$ROOT/src/revoscan_launcher/entrypoint.py"

mkdir -p "$APPDIR/usr/bin" \
         "$APPDIR/usr/share/applications" \
         "$APPDIR/usr/share/icons/hicolor/scalable/apps" \
         "$APPDIR/usr/share/vulkan/explicit_layer.d" \
         "$APPDIR/usr/share/doc/revoscan-linux-launcher" \
         "$APPDIR/usr/share/licenses/revoscan-linux-launcher" \
         "$APPDIR/opt"
cp "$ROOT/build/pyinstaller-dist/revoscan-launcher" "$APPDIR/usr/bin/revoscan-launcher"
cp "$ROOT/packaging/AppRun" "$APPDIR/AppRun"
chmod 755 "$APPDIR/AppRun" "$APPDIR/usr/bin/revoscan-launcher"
cp "$ROOT/packaging/revoscan-linux-launcher.desktop" "$APPDIR/revoscan-linux-launcher.desktop"
cp "$ROOT/packaging/revoscan-linux-launcher.desktop" "$APPDIR/usr/share/applications/revoscan-linux-launcher.desktop"
cp "$ROOT/packaging/revoscan-linux-launcher.svg" "$APPDIR/revoscan-linux-launcher.svg"
cp "$ROOT/packaging/revoscan-linux-launcher.svg" "$APPDIR/usr/share/icons/hicolor/scalable/apps/revoscan-linux-launcher.svg"
ln -sfn revoscan-linux-launcher.svg "$APPDIR/.DirIcon"
cp "$ROOT/LICENSE" "$APPDIR/usr/share/licenses/revoscan-linux-launcher/LICENSE"
cp "$ROOT/vendor/Vulkan-Headers/LICENSE.md" "$APPDIR/usr/share/licenses/revoscan-linux-launcher/Vulkan-Headers-LICENSE.md"
cp "$ROOT/packaging/third-party-notices.txt" "$APPDIR/usr/share/doc/revoscan-linux-launcher/THIRD-PARTY-NOTICES.txt"
cp "$ROOT/README.md" "$APPDIR/usr/share/doc/revoscan-linux-launcher/README.md"
cp "$ROOT/src/vulkan_layer/VK_LAYER_REVOSCAN_LINUX_GPU_MAP.json" "$APPDIR/usr/share/vulkan/explicit_layer.d/"
"$ROOT/scripts/build-layer.sh" "$APPDIR/usr/share/vulkan/explicit_layer.d/librevoscan_gpu_map.so"
cp -a /opt/wine-staging "$APPDIR/opt/"
# Revo Scan is x86_64-only. Use Wine's 64-bit WoW64 path and avoid requiring host i386 glibc.
rm -rf "$APPDIR/opt/wine-staging/lib/wine/i386-unix"
ln -sfn ../../opt/wine-staging/lib/wine/x86_64-unix/wine "$APPDIR/usr/bin/wine64"
ln -sfn ../../opt/wine-staging/bin/wineserver "$APPDIR/usr/bin/wineserver64"

# Never ship Wine's Bluetooth driver. When a host BlueZ radio exists, the
# winebth driver exposes it and Revo Scan's simpleble.dll hits still-stubbed
# WinRT Bluetooth APIs (E_NOTIMPL), whose exception escapes rvscan plugin
# activation and kills the app before its window maps. Without a radio the app
# logs "BluetoothManager init error" and continues. See PROGRESS.md.
rm -f "$APPDIR/opt/wine-staging/lib/wine/x86_64-windows/winebth.sys" \
      "$APPDIR/opt/wine-staging/lib/wine/i386-windows/winebth.sys" \
      "$APPDIR/opt/wine-staging/lib/wine/x86_64-unix/winebth.so" \
      "$APPDIR/opt/wine-staging/lib/wine/i386-unix/winebth.so"

for notice in /usr/share/doc/wine-staging/copyright \
              /usr/share/doc/wine-staging-amd64/copyright \
              /usr/share/doc/python3.10/copyright \
              /usr/share/doc/tcl8.6/copyright \
              /usr/share/doc/tk8.6/copyright; do
    if [[ -f "$notice" ]]; then
        cp "$notice" "$APPDIR/usr/share/licenses/revoscan-linux-launcher/$(basename "$(dirname "$notice")").copyright"
    fi
done
if [[ -f "$VENV/lib/python3.10/site-packages/PyInstaller/LICENSE.txt" ]]; then
    cp "$VENV/lib/python3.10/site-packages/PyInstaller/LICENSE.txt" "$APPDIR/usr/share/licenses/revoscan-linux-launcher/PyInstaller-LICENSE.txt"
fi
CERTIFI_LICENSE=$("$VENV/bin/python" -c 'from importlib.metadata import distribution; d=distribution("certifi"); print(d.locate_file(next(f for f in d.files if str(f).endswith("/licenses/LICENSE"))))')
if [[ -f "$CERTIFI_LICENSE" ]]; then
    cp "$CERTIFI_LICENSE" "$APPDIR/usr/share/licenses/revoscan-linux-launcher/certifi-LICENSE"
fi

if [[ ! -x "$APPIMAGE_TOOL" ]]; then
    curl -fL --retry 2 --connect-timeout 20 \
        -o "$APPIMAGE_TOOL" \
        https://github.com/AppImage/appimagetool/releases/download/continuous/appimagetool-x86_64.AppImage
    chmod 755 "$APPIMAGE_TOOL"
fi
python3 "$ROOT/scripts/audit_public_artifact.py" "$APPDIR"
APPIMAGE_EXTRACT_AND_RUN=1 ARCH=x86_64 \
    "$APPIMAGE_TOOL" --no-appstream "$APPDIR" "$OUT"
python3 "$ROOT/scripts/audit_public_artifact.py" "$OUT"

set +e
timeout 10s xvfb-run -a env APPIMAGE_EXTRACT_AND_RUN=1 "$OUT"
smoke_status=$?
set -e
if [[ $smoke_status -ne 124 ]]; then
    printf 'Launcher GUI smoke test returned %s (expected timeout 124 while its event loop remains open).\n' "$smoke_status" >&2
    exit 1
fi
printf 'Built and smoke-tested public AppImage: %s\n' "$OUT"

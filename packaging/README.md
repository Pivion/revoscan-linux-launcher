# AppImage packaging notes

The public AppImage must start `AppRun` and therefore the launcher GUI first. It contains the launcher, its Python/Tk runtime, Wine 64-bit runtime, the Vulkan layer, and license/source notices. It does **not** contain any Revopoint installer, Revo Scan application directory, Wine prefix, or user data.

Build dependencies and Wine must be staged from the pinned Ubuntu baseline container (see `Containerfile.ubuntu22`). Do not copy the local Fedora Wine AppDir into a public build: its ABI was only tested on the build host. The host provides Mesa/RADV/Intel Vulkan drivers and device permissions; those are not copied into the AppImage.

The layer manifest uses a relative library name. `AppRun`/`runtime.py` add the layer directory to `LD_LIBRARY_PATH`; this was exercised with `vulkaninfo` on the local AMD Radeon 780M. The mapping is set only for a user-selected AMD/Intel adapter and target.

## Public build status

The source, GUI, installer logic, mapping core, tests, and public-payload audit exist. The clean multi-distro AppImage builder and distro matrix are still in progress. No public release is authorized until the payload audit and all pinned distro smoke tests pass.

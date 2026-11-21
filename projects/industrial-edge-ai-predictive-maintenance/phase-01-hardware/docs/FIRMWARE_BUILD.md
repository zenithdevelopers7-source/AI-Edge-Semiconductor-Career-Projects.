# ESP32 build preparation — no hardware required

This compiles the existing classic ESP32 `esp32dev` target for the same selected hardware. It does not upload firmware, open a serial port, detect your ordered board revision, test sensors or run a motor. Exact board compatibility and all physical commissioning remain pending hardware receipt and inspection.

The build tool is fixed to PlatformIO Core 6.2.0 and the development platform to Espressif32 6.13.0. Direct library versions are fixed in `firmware/platformio.ini`, replacing floating ranges. The platform's Arduino framework is 2.0.17. This is a controlled compile configuration, not a hermetic or byte-identical release guarantee: Python packages, platform tool dependencies, package distribution and host differences still need release qualification.

The former INA219 requirement `^3.0.1` is unavailable in the published Adafruit INA219 package. It is corrected to `1.2.3` for the same sensor library; the shared Adafruit BusIO dependency is also fixed explicitly. This changes software dependencies only.

## Windows: compile only

Run from `phase-01-hardware`, preferably with Python 3.12. Use a separate environment so dashboard dependencies remain unchanged. The first build downloads the compiler/framework and libraries and needs internet access and disk space.

```powershell
python -m venv .build-env
.\.build-env\Scripts\python.exe -m pip install -r requirements-build.txt
$env:PLATFORMIO_SETTING_ENABLE_TELEMETRY = "No"
$env:PLATFORMIO_DISABLE_UPGRADE_CHECK = "true"
.\.build-env\Scripts\python.exe -m platformio run --project-dir firmware --environment esp32dev
```

On Linux, use `.build-env/bin/python` and shell-appropriate environment-variable syntax. Build caches are local and are not part of the arrival pack. Do not run an upload or monitor target during preparation.

### Windows compiler-path workaround

The initial Windows build encountered `CreateProcess: No such file or directory` with long compiler/project paths. The same source compiled successfully using a temporary short drive mapping for both the project and tool cache. If this happens, use an unused drive letter (R: below) from `phase-01-hardware`; never replace an existing mapping. Run only one build at a time. This maps the existing folder and adds no hardware or permanent system installation:

```powershell
if (Test-Path R:\) { throw "R: is already in use; choose an unused drive letter." }
subst R: (Get-Location).Path
if ($LASTEXITCODE -ne 0) { throw "Could not create the temporary mapping." }
$savedCoreDirectory = $env:PLATFORMIO_CORE_DIR
try {
    $env:PLATFORMIO_CORE_DIR = "R:\.platformio-core"
    .\.build-env\Scripts\python.exe -m platformio run --project-dir R:\firmware --environment esp32dev
    if ($LASTEXITCODE -ne 0) { throw "Firmware compilation failed; review the build log." }
} finally {
    if ($null -eq $savedCoreDirectory) {
        Remove-Item Env:PLATFORMIO_CORE_DIR -ErrorAction SilentlyContinue
    } else {
        $env:PLATFORMIO_CORE_DIR = $savedCoreDirectory
    }
    subst R: /D
}
```

The cache is kept in the current folder and may download tools again on first use. The previous `PLATFORMIO_CORE_DIR` setting is restored. Remove the temporary drive mapping only after the build exits; no project files are deleted by removing that mapping. The project's `.gitignore` excludes local build/cache/environment files.

After a successful build, record hashes using the same environment:

```powershell
.\.build-env\Scripts\python.exe scripts/record_firmware_build.py
```

The record is `firmware/build-evidence.json`. It includes the source/configuration and four build-output hashes, build-tool version and explicit false physical-readiness flags. It refuses an existing record: archive the previous record separately before creating another. Keep the successful build log with the record. The recording script only inventories existing files; it does not prove that they were produced by the current source or that compilation succeeded. The compiler/job result supplies that evidence.

## GitHub verification

The `esp32-firmware-build` job in EDGEOPS Dashboard Checks installs the fixed build tool, compiles with no upload target, creates a hash record only after success and retains `edgeops-esp32-compile-only` artifacts for 14 days. These artifacts contain firmware binaries/ELF plus the record; they are build outputs for review, not an approved deployment package. A later source/configuration change needs a fresh successful build. Do not infer the latest result from an earlier successful run.

No firmware control pins or new hardware are added by this work. GPIO21/22/4, USB serial 115200 baud, sensor-quality flags and nominal 1 Hz V1 output remain the current source behavior. Timing, calibration, fault behavior, power-up state, sensor accuracy and long-duration reliability need physical verification. Measured ingestion and motor control remain separate, unimplemented commissioning steps.

## Observed local result — 20 November 2026

The existing target compiled successfully on Windows after the dependency correction and short-path workaround. The compiler reported 21,976 bytes of RAM (6.7%) and 306,993 bytes of flash (23.4%) for this configuration. These are build-reported resource estimates, not measured runtime consumption. Firmware, bootloader, partition and ELF files were produced. No upload, connected-device test or equipment operation was performed.

## Build configuration references

- [Espressif32 6.13.0 platform release](https://github.com/platformio/platform-espressif32/releases/tag/v6.13.0)
- [PlatformIO build command](https://docs.platformio.org/en/latest/core/userguide/cmd_run.html)
- [PlatformIO library dependencies](https://docs.platformio.org/en/latest/projectconf/sections/env/options/library/lib_deps.html)

# Orange Pi Zero 2 OpenBMC port

This repository contains the Orange Pi Zero 2 (Allwinner H616) OpenBMC porting
layer and the reproducible build inputs. The upstream OpenBMC tree is included
under `openbmc/`; board-specific work is under `meta-orangepi/`.

## Board scope

- Machine: `orangepi-zero2`
- SoC: Allwinner H616
- RAM variants: 512 MB and 1 GB (the machine configuration uses the common
  hardware description; memory sizing is detected at runtime)
- GPIO control: packaged through the OpenBMC service layer
- MS2130 USB capture: packaged as a systemd service and exposed through the
  board layer
- USB keyboard/mouse control is intentionally left for a later USB MCU phase

## Source revisions

See [`sources/versions.txt`](sources/versions.txt) for the exact upstream
repositories and commits used for the Linux, U-Boot, and OpenBMC trees.

## Build

On a supported x86_64 Linux build host, enter `openbmc/` and run:

```sh
MACHINE=orangepi-zero2 DISTRO_FEATURES:append=" systemd" \
    TEMPLATECONF=meta-orangepi/conf/templates/default \
    . ./setup orangepi-zero2 build-orangepi-zero2
bitbake obmc-phosphor-image
```

The helper scripts in `scripts/` document the dependency bootstrap used on
the shared cluster. Do not place SSH keys or GitHub tokens in this repository.

## Current artifacts

`artifacts/orangepi-zero2-linux/` contains the verified standalone H616 Linux
build output (`Image`, DTB, `System.map`, and kernel config). The full
OpenBMC image remains a build target; it is not claimed as complete until a
successful BitBake image and its checksum are present.


# Orange Pi Zero 2 OpenBMC port / Orange Pi Zero 2 OpenBMC 移植

This repository contains the Orange Pi Zero 2 (Allwinner H616) OpenBMC porting
layer and reproducible GitHub Actions build inputs. The upstream OpenBMC tree
is included under `openbmc/`; board-specific work is under `meta-orangepi/`.

本仓库包含 Orange Pi Zero 2（全志 H616）的 OpenBMC 移植层，以及可复现的
GitHub Actions 构建输入。上游 OpenBMC 源码位于 `openbmc/`，板级定制内容位于
`meta-orangepi/`。

## Board scope / 板卡范围

- Machine: `orangepi-zero2`
- SoC: Allwinner H616
- RAM variants: 512 MB and 1 GB (the machine configuration uses the common
  hardware description; memory sizing is detected at runtime)
- GPIO control: packaged through the OpenBMC service layer
- MS2130 USB capture: packaged as a systemd service and exposed through the
  board layer
- USB keyboard/mouse control is intentionally left for a later USB MCU phase

板卡信息：

- 机器配置：`orangepi-zero2`
- SoC：全志 H616
- 内存版本：512 MB 和 1 GB（机器配置使用通用硬件描述，运行时识别内存容量）
- GPIO 控制：通过 OpenBMC 服务层打包
- MS2130 USB 采集：打包为 systemd 服务，并由板级层提供
- USB 键盘/鼠标控制暂留到后续 USB 单片机阶段

## Source revisions / 源码版本

See [`sources/versions.txt`](sources/versions.txt) for the exact upstream
repositories and commits used for the Linux, U-Boot, and OpenBMC trees.

具体的 Linux、U-Boot 和 OpenBMC 上游仓库及提交版本见
[`sources/versions.txt`](sources/versions.txt)。

## GitHub Actions build / GitHub Actions 构建

The workflow is defined in
[`build-orangepi-zero2.yml`](.github/workflows/build-orangepi-zero2.yml). It
builds standalone Linux and U-Boot first, then builds the full OpenBMC image
and uploads the TF-card image as an artifact.

工作流位于
[`build-orangepi-zero2.yml`](.github/workflows/build-orangepi-zero2.yml)。它会先编译
独立 Linux 和 U-Boot，再编译完整 OpenBMC，并将 TF 卡镜像作为 Actions artifact
上传。

## Local build / 本地构建

On a supported x86_64 Linux build host, enter `openbmc/` and run the following
commands. 在支持的 x86_64 Linux 编译机上进入 `openbmc/`，执行：

```sh
MACHINE=orangepi-zero2 DISTRO_FEATURES:append=" systemd" \
    TEMPLATECONF=meta-orangepi/conf/templates/default \
    . ./setup orangepi-zero2 build-orangepi-zero2
bitbake obmc-phosphor-image
```

The helper scripts in `scripts/` document the dependency bootstrap used on
the shared cluster. Do not place SSH keys or GitHub tokens in this repository.

`scripts/` 中的辅助脚本记录了共享集群上的依赖准备方式。不要把 SSH 私钥或
GitHub token 放入本仓库。

## Current artifacts / 当前产物

`artifacts/orangepi-zero2-linux/` contains the verified standalone H616 Linux
build output (`Image`, DTB, `System.map`, and kernel config). The full
OpenBMC image remains a build target; it is not claimed as complete until a
successful BitBake image and its checksum are present.

`artifacts/orangepi-zero2-linux/` 包含已经校验的 H616 独立 Linux 编译产物
（`Image`、DTB、`System.map` 和内核配置）。完整 OpenBMC 镜像仍需通过 BitBake
成功构建并生成校验和后，才能宣布完成。

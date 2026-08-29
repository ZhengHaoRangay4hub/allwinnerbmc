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
repositories and commits used for Linux, U-Boot, Trusted Firmware-A, and OpenBMC.

具体的 Linux、U-Boot、Trusted Firmware-A 和 OpenBMC 上游仓库及提交版本见
[`sources/versions.txt`](sources/versions.txt)。

## GitHub Actions build / GitHub Actions 构建

The workflow is defined in
[`build-orangepi-zero2-image.yml`](.github/workflows/build-orangepi-zero2-image.yml). It
prepares the board Linux configuration, verifies the OpenBMC boot components,
finishes the reusable Node.js host-tool cache, then lets BitBake build the complete
OpenBMC image (including the boot components required inside that image) and
uploads one directly flashable `.wic` TF-card image, `SHA256SUMS`, and a
read-only image validation report.

工作流位于
[`build-orangepi-zero2-image.yml`](.github/workflows/build-orangepi-zero2-image.yml)。它先准备板级
Linux 配置并检查 OpenBMC 启动组件，先完成可复用的 Node.js 主机构建工具缓存，
再由 BitBake 编译完整 OpenBMC（镜像内部仍包含启动所必需的启动组件），
最后上传一个可直接烧录的 `.wic` TF 卡镜像、`SHA256SUMS` 和镜像校验报告。

The boot check, native-tool cache, and full-image stages share a 330-minute budget inside a
360-minute job. The remaining 30 minutes cover setup, graceful termination,
cache/log saving, and artifact validation/upload. A controlled timeout
can dispatch up to five continuation runs if the cache was saved. Actual
recipe errors and early SIGTERM/SIGKILL exits remain failures. Downloads and
completed sstate tasks are reusable; an unfinished compiler task does not
resume at an instruction-level breakpoint. The full image uses `bitbake -k`
so unrelated recipes can finish producing reusable sstate after another fails.

启动检查、原生工具缓存与完整镜像编译共享 330 分钟预算，Job 上限为 360 分钟；其余 30 分钟用于
环境准备、正常终止、保存缓存与日志，以及镜像校验和上传。正常预算到期且缓存
保存成功时，最多自动续编五轮；真实配方错误
及提前发生的 SIGTERM/SIGKILL 仍判为失败。可复用下载文件和已完成的 sstate 任务，
未完成的编译任务不能在指令级断点续跑。完整镜像使用 `bitbake -k`，让不受错误影响的
配方继续完成缓存生成。

Before the full image, CI runs `bitbake nodejs-native:do_populate_sysroot`.
This completes the Web UI's expensive host tool through its sstate-producing
task before kernel compilation competes for the same four CPUs. It keeps
`PARALLEL_MAKE=-j4`; the stage order does not change recipe sources or discard
compatible caches. A cached Node.js sysroot is reused. If this stage reaches
the shared deadline, CI saves its completed caches and continues in another
run without starting the full image. It is skipped in board-preflight mode.
It does not produce a flashable image, and cannot preserve unfinished compiler
objects when interrupted; only completed sstate tasks can be reused.

完整镜像阶段前，CI 先执行 `bitbake nodejs-native:do_populate_sysroot`，让 Web 界面
依赖的耗时主机工具先完成到可生成 sstate 缓存的阶段，再开始内核编译。单个任务仍使用
`PARALLEL_MAKE=-j4`；这里只改变顺序，不修改配方源码或丢弃兼容缓存，已有的 Node.js
缓存可直接复用。若该阶段耗尽共享预算，则保存已完成的缓存并续编，不再启动完整镜像
阶段；板级预检模式跳过此步骤。这个阶段本身不生成刷写镜像，也不能保留中断时尚未
完成的编译对象，仍然只能复用已完成的 sstate 任务。

The CI cache also retains the local hash-equivalence database alongside
sstate. This preserves mappings used to reuse equivalent build outputs
after metadata changes; identical cached tasks remain reusable as before.

CI 同时把哈希等价数据库保存在 sstate 缓存目录，保留元数据变化后判断构建结果
是否可复用的映射；完全相同任务的现有缓存仍可正常沿用。

The kernel and U-Boot use pinned Git recipes with shallow downloads and
normal sstate support. The earlier `externalsrc` mode explicitly disabled
sstate creation for these recipes. Its old build directories cannot be
recovered from sstate: the first standard-recipe build creates that cache;
other completed, compatible recipe caches can still be reused.

内核与 U-Boot 使用固定 Git 提交、浅下载和正常 sstate 缓存。此前的 `externalsrc`
模式明确禁用了这两个配方的 sstate 生成，旧构建目录不能从缓存恢复；切换后的
第一次构建才会生成可复用缓存。其他已完成且兼容的配方缓存仍可沿用。

The optional workflow input `preflight_only` validates boot recipes, compiles
the capture helper with its strict warning flags, installs the GPIO helper,
and checks the fetched kernel configuration. It also compiles representative
vendor Wi-Fi and CPU-frequency objects with the actual Yocto compiler. The
independent concurrency group does not cancel a full image build. Preflight
only reads caches, never dispatches a full-image continuation, and produces
no firmware artifacts. Passing it does not mean the full kernel or OpenBMC
image has been built.

可选输入 `preflight_only` 验证启动配方、按严格警告选项编译采集程序、检查 GPIO
工具安装和实际内核配置，并使用真正的 Yocto 编译器编译厂商 Wi-Fi 与调频驱动的
代表性目标文件。它使用独立并发组，不取消正在进行的完整镜像构建；只读取缓存，
不自动续跑完整镜像，也不上传固件产物。预检通过不代表完整内核或 OpenBMC 镜像
已经编译完成。

BL31 is built for `sun50i_h616` as an internal dependency and included in the
combined SPL/U-Boot payload at the TF card's 8 KiB offset. The boot partition
contains Image, the Zero 2 device tree, and extlinux.conf. The second partition
is the ext4 OpenBMC root filesystem; no initramfs is needed to resolve its
`/dev/mmcblk0p2` root argument. Separate Linux/U-Boot deliverables are not uploaded.

BL31 使用 `sun50i_h616` 平台编译，作为内部依赖放入 TF 卡 8 KiB 偏移处的 SPL/U-Boot
组合启动程序。启动分区包含 Image、Zero 2 设备树和 extlinux.conf；第二分区是 ext4
OpenBMC 根文件系统，`/dev/mmcblk0p2` 根分区参数无需 initramfs 解析。
工作流不再单独上传 Linux/U-Boot 交付物。

The boot partition also contains a CRC-protected `uboot.env`, generated from
the compiled bootloader's defaults. Userspace uses actual `libubootenv`
utilities and `/etc/fw_env.config` to access `/boot/uboot.env`, without
writing raw card offsets. Services that need it require the boot mount.

启动分区另含从当前 U-Boot 默认配置生成、带 CRC 校验的 `uboot.env`。
用户态使用真正的 `libubootenv` 工具，并通过 `/etc/fw_env.config` 访问
`/boot/uboot.env`，不写裸卡偏移；相关服务要求先挂载启动分区。

Before uploading, the workflow checks the MBR partition layout, the SPL at
8 KiB and its checksum, the embedded U-Boot/BL31 FIT payloads, the boot files,
and the ext4 filesystem. It also verifies that the root filesystem contains
OpenBMC, AArch64 systemd/bmcweb, and the Web UI. A `.verification.json` report
accompanies the image. These checks do not replace boot testing on physical
512 MB and 1 GB boards.

上传前，工作流会检查 MBR 分区、8 KiB 处的 SPL 及其校验和、内嵌的 U-Boot/BL31
FIT 数据、启动文件和 ext4 文件系统，并确认根文件系统包含 OpenBMC、AArch64 版
systemd/bmcweb 及 Web UI。镜像附带 `.verification.json` 校验报告。
这些检查不能替代 512 MB 和 1 GB 实板的启动测试。

To repeat the read-only checks on an existing image, install Python 3.11+,
`mtools`, `device-tree-compiler`, and `e2fsprogs`, then run:
复查已有镜像时，安装上述工具后执行（不挂载镜像，也不写入 TF 卡）：

```sh
python3 scripts/verify-tf-image.py /path/to/openbmc.wic
```

## Local build / 本地构建

Use a supported x86_64 Linux build host. First follow the workflow's source
checkout, patch, and defconfig generation steps, then copy the board layer
into `openbmc/`. 在支持的 x86_64 Linux 编译机上，先按工作流准备源码、应用补丁并
生成 defconfig，再复制板级层并初始化：

```sh
cp -a meta-orangepi openbmc/meta-orangepi
cd openbmc
TEMPLATECONF=meta-orangepi/conf/templates/default \
    . ./setup orangepi-zero2 build-orangepi-zero2
```

Before running `bitbake obmc-phosphor-image`, replace the historical cluster
paths in `conf/local.conf` with your source, build, download, and sstate paths.
For direct Internet access clear both `PREMIRRORS` and `PREMIRRORS:prepend`.
GitHub Actions already overrides these values and uses upstream sources directly.

执行 `bitbake obmc-phosphor-image` 前，需要把 `conf/local.conf` 中历史集群的源码、
构建及缓存路径改为本机路径。使用直连网络时同时清空 `PREMIRRORS` 与
`PREMIRRORS:prepend`。GitHub Actions 已覆盖这些配置，直接使用上游源。

The helper scripts in `scripts/` document the dependency bootstrap used on
the shared cluster. Do not place SSH keys or GitHub tokens in this repository.

`scripts/` 中的辅助脚本记录了共享集群上的依赖准备方式。不要把 SSH 私钥或
GitHub token 放入本仓库。

## Released TF-card image / 已发布 TF 卡镜像

The first complete OpenBMC TF-card image is published in the
[`openbmc-orangepi-zero2-20260829`](https://github.com/ZhengHaoRangay4hub/allwinnerbmc/releases/tag/openbmc-orangepi-zero2-20260829)
release. It was built by
[GitHub Actions run 17](https://github.com/ZhengHaoRangay4hub/allwinnerbmc/actions/runs/33222879648)
from commit `dd9b3362`.

首个完整 OpenBMC TF 卡镜像已发布到
[`openbmc-orangepi-zero2-20260829`](https://github.com/ZhengHaoRangay4hub/allwinnerbmc/releases/tag/openbmc-orangepi-zero2-20260829)
Release。该镜像由
[GitHub Actions 第 17 轮](https://github.com/ZhengHaoRangay4hub/allwinnerbmc/actions/runs/33222879648)
基于提交 `dd9b3362` 构建。

- Image / 镜像：
  [`obmc-phosphor-image-orangepi-zero2-20260829002057.wic`](https://github.com/ZhengHaoRangay4hub/allwinnerbmc/releases/download/openbmc-orangepi-zero2-20260829/obmc-phosphor-image-orangepi-zero2-20260829002057.wic)
- Size / 大小：`324259840` bytes（约 309.2 MiB）
- SHA-256：`6e64a4fbbb5e672726482a69480c8b7305ea134c7557e49dbb293cd0b58a6aa8`
- Checksum file / 校验文件：
  [`SHA256SUMS`](https://github.com/ZhengHaoRangay4hub/allwinnerbmc/releases/download/openbmc-orangepi-zero2-20260829/SHA256SUMS)
- Verification report / 校验报告：
  [`obmc-phosphor-image-orangepi-zero2-20260829002057.wic.verification.json`](https://github.com/ZhengHaoRangay4hub/allwinnerbmc/releases/download/openbmc-orangepi-zero2-20260829/obmc-phosphor-image-orangepi-zero2-20260829002057.wic.verification.json)

This is one directly flashable whole-card image for both the 512 MB and 1 GB
Orange Pi Zero 2 variants. Linux, the device tree, U-Boot, BL31, the boot
environment, and the OpenBMC root filesystem are integrated into the image;
they are not separate release assets. CI and an independent macOS recheck
produced identical verification reports and matching SHA-256 values.

这是同时用于 Orange Pi Zero 2 512 MB 与 1 GB 版本的单一整卡镜像，可直接写入
TF 卡。Linux、设备树、U-Boot、BL31、启动环境和 OpenBMC 根文件系统均已集成在
镜像内，不作为独立 Release 产物发布。CI 校验与 macOS 本地复验报告完全一致，
SHA-256 也与发布清单相符。

Before writing the image, verify `SHA256SUMS` and carefully confirm the target
device. Imaging tools such as balenaEtcher can write the `.wic` file directly;
advanced users may use `dd` against the entire card device, not a partition.
Selecting the wrong device destroys its contents. Physical boot testing on
both RAM variants has not yet been performed.

烧录前请先核对 `SHA256SUMS`，并仔细确认目标设备。balenaEtcher 等镜像工具可以
直接写入 `.wic`；使用 `dd` 时必须选择整张 TF 卡设备而不是某个分区。选错设备会
覆盖其中的数据。目前尚未在两种内存版本的实板上完成启动测试。

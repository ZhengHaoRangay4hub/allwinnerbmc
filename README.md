# Orange Pi Zero 2 OpenBMC

[中文说明](#中文说明) | [English documentation](#english-documentation)

This repository ports OpenBMC to the Orange Pi Zero 2 (Allwinner H616) and
adds an MS2130 video path plus a CH32V307 keyboard/absolute-mouse bridge.

本仓库将 OpenBMC 移植到 Orange Pi Zero 2（全志 H616），并加入 MS2130 视频采集
与 CH32V307 键盘/绝对坐标鼠标桥。

---

# 中文说明

## 1. 项目概览

本项目面向 Orange Pi Zero 2 的 512 MiB 和 1 GiB 两种内存版本。两种板卡使用同一
机器配置、设备树和整卡镜像，DRAM 容量由启动程序在运行时识别。目标处理器是
Allwinner H616，4 核 Cortex-A53、ARMv8-A/AArch64。

仓库提供：

- 基于 Yocto/OpenBMC 的 `orangepi-zero2` 机器层；
- Linux 6.1、U-Boot 2021.10 和 Trusted Firmware-A 2.14.2 的固定源码版本；
- 可直接写入 TF 卡的完整 `.wic` 镜像；
- MS2130 USB HDMI 采集卡到 OpenBMC WebUI KVM 的视频链路；
- WCH-LinkE 自动识别和 CH32V307 复合 USB HID 键盘/绝对坐标鼠标固件；
- 简体中文 WebUI 语言包；
- GitHub Actions 可续编构建、镜像结构检查和 SHA-256 校验。

固定的上游仓库、分支和提交见 [sources/versions.txt](sources/versions.txt)。板级内容位于
`meta-orangepi/`，CH32V307 固件位于 `firmware/ch32v307-kvm/`，OpenBMC 上游树位于
`openbmc/`。

## 2. 系统架构

```text
                            Orange Pi Zero 2 / OpenBMC
┌──────────────┐   HTTPS   ┌───────────────────────────────┐
│ 浏览器 WebUI │◄─────────►│ bmcweb + webui-vue + noVNC   │
└──────┬───────┘           └──────────────┬────────────────┘
       │ 网页鼠标/键盘                    │ RFB / KVM
       │                                  ▼
       │                    ┌───────────────────────────────┐
       │                    │ obmc-ikvm                     │
       │                    │ 视频：V4L2 MJPEG              │
       │                    │ 输入：绝对坐标 + 键盘报告      │
       │                    └──────────┬───────────▲────────┘
       │                               │           │
       │            串口控制帧 921600  │           │ MJPEG
       │                               ▼           │
       │                    ┌────────────────┐   ┌──┴───────────┐
       │                    │ WCH-LinkE CDC  │   │ MS2130 UVC   │◄── HDMI
       │                    │ /dev/ttyACM*   │   │ /dev/video0  │
       │                    └───────┬────────┘   └──────────────┘
       │                            │ USART1 PA9/PA10
       │                            ▼
       │                    ┌────────────────┐      P6 USB
       └───────────────────►│ CH32V307       │──────────────► 被控主机
                            │ 键盘 + 绝对鼠标 │                 USB HID
                            └────────────────┘
```

启动介质是标准 MBR 分区的 TF 卡：

- 8 KiB 偏移：`u-boot-sunxi-with-spl.bin`，内含 SPL、U-Boot 和 BL31；
- 第 1 分区：FAT 启动分区，包含 Linux `Image`、H616 设备树、`extlinux.conf` 和
  `uboot.env`；
- 第 2 分区：ext4 OpenBMC 根文件系统；
- 根文件系统直接使用 `/dev/mmcblk0p2`，不依赖 initramfs。

## 3. KVM 视频和绝对坐标键鼠

### 视频链路

MS2130 作为标准 UVC/V4L2 设备连接 Orange Pi。`uvcvideo` 提供 `/dev/video0`，
`obmc-ikvm` 读取设备实际协商的 MJPEG 宽度、高度和像素格式，并将视频送入现有
WebUI KVM。分辨率不固定为 1080p；输入源切换分辨率后，服务按 V4L2 协商结果更新
帧缓冲。具体可用分辨率仍取决于 MS2130 固件、HDMI 源和 USB 带宽。

### 坐标链路

正式 WebUI 使用一套端点精确的绝对坐标：

```text
浏览器画布坐标
  -> noVNC 反向换算为 MS2130 帧缓冲坐标
  -> obmc-ikvm 对每个轴钳位并映射到 0..32767
  -> WCH-LinkE CDC 串口帧
  -> CH32V307 P6 绝对坐标 USB HID 鼠标
  -> 被控主机光标
```

noVNC 只缩放显示画布，不调整远端会话分辨率，也不启用画布拖动。`obmc-ikvm` 使用
64 位中间值和四舍五入，将帧缓冲第一个像素精确映射为 `0`，最后一个像素精确映射为
`32767`；越界值先钳位。因此浏览器尺寸、CSS 缩放和采集分辨率变化不会改变网页指针
与被控机指针的坐标关系。

CH32V307 在面向被控机的 P6 USB 口上枚举两个 HID 接口：

- Boot Keyboard：8 字节键盘报告；
- Absolute Mouse：6 字节报告，格式为 `buttons, x_le16, y_le16, wheel`。

控制协议使用 USART1、921600 baud、8-N-1：

```text
A5 5A | version | type | sequence | length | payload | crc16_le
```

CRC 使用 CRC-16/CCITT-FALSE。消息类型包括键盘、指针、心跳和 release-all。控制链路
静默超过 1 秒时，CH32V307 会释放全部按键和鼠标按钮，避免断线卡键。

### WCH-LinkE 与 CH32V307 接线

在 CH32V307V EVT 板 J2 上安装 UART 跳线：

- WCH-LinkE `RX_OUT` → CH32V307 `TX1` / PA9；
- WCH-LinkE `TX_OUT` → CH32V307 `RX1` / PA10；
- WCH-LinkE USB → Orange Pi Zero 2；
- CH32V307 P6 USB Device → 被控主机；
- 串口使用 3.3 V 电平。

OpenBMC 通过 USB VID/PID `1a86:8010` 查找 WCH-LinkE，只接受对应的 `ttyACM*`
设备，不依赖易变化的 `/dev/ttyACM0` 编号。热拔插后服务会周期性重新发现设备。

## 4. 已集成的硬件和驱动

| 模块 | 内核/用户态组件 | 当前状态 |
| --- | --- | --- |
| H616 CPU | ARM64、SMP、Cortex-A53、CPUFreq/OPP | 已编译；默认 ondemand 调频 |
| TF 卡 | `MMC_SUNXI`、MBR、VFAT、ext4 | 已编译并由镜像检查器验证 |
| 时钟/电源 | SUNXI CCU、H6 R-CCU、DE2 CCU、H616 pinctrl | 已编译 |
| 温度/看门狗/RTC | `SUN8I_THERMAL`、`SUNXI_WATCHDOG`、`RTC_DRV_SUN6I` | 已编译 |
| 有线网络 | STMMAC、`DWMAC_SUN8I`、AC200、Realtek/Motorcomm PHY | 驱动已包含 |
| 板载 Wi-Fi | UWE5622、`sprdwl_ng`、cfg80211、rfkill、固件、wpa_supplicant | 已集成；此前在实板连接 Wi-Fi 验证 |
| USB Host | xHCI、EHCI、OHCI、USB Storage、USB HID、USB Audio | 已编译 |
| MS2130 视频 | `uvcvideo`、V4L2、MJPEG、`obmc-ikvm` | 已集成；此前在 512 MiB 实板热部署验证 |
| WCH-LinkE | `cdc_acm`、VID/PID 自动发现、`ttyACM*` 重连 | 已集成；USART1 通信已用硬件断点验证 |
| CH32V307 HID | P6 复合键盘/绝对鼠标、串口心跳和断线释放 | 固件已编译、烧写并在主机侧枚举验证 |
| GPIO | GPIO character device、libgpiod 工具和板级服务 | 已集成 |
| Web 管理 | bmcweb、webui-vue、noVNC、简体中文语言包 | 已集成 |

“已编译/已集成”表示对应配置、模块或软件包存在于构建输入并通过 CI 构建；它不自动
等同于当前 Release 已在所有外设组合上完成实板回归。最新整卡镜像尚需重新烧录，分别
在 512 MiB 和 1 GiB 板卡上做完整启动、网络、视频和键鼠测试。

## 5. 最新 Release

最新版本：
[openbmc-orangepi-zero2-20260901-wchlinke-kvm](https://github.com/ZhengHaoRangay4hub/allwinnerbmc/releases/tag/openbmc-orangepi-zero2-20260901-wchlinke-kvm)

- OpenBMC 镜像源码提交：`3c9089d3d69afec13805aee44307eb6493ccdbd9`；
- 构建任务：[GitHub Actions #27](https://github.com/ZhengHaoRangay4hub/allwinnerbmc/actions/runs/33421854269)；
- 整卡镜像：`obmc-phosphor-image-orangepi-zero2-20260831175858.wic`；
- 镜像大小：`336955392` 字节；
- 镜像 SHA-256：`fe57948c2166e590d26fd29fb69e9b52180bc24609d46acd2aebe7caa6dfc366`；
- CH32V307 BIN SHA-256：`19aec3e70e5c07ca958be0f2b348262b49720837bc6d1cbbd83072642de1c4d5`。

Release 同时提供 `.wic`、`SHA256SUMS`、镜像验证 JSON、CH32V307 `.bin` 和 `.hex`。
`.wic` 是同时适用于 512 MiB 和 1 GiB 版本的整卡镜像，已经包含 Linux、设备树、
U-Boot、BL31、启动环境和 OpenBMC 根文件系统。

## 6. 编译机要求

OpenBMC/Yocto 应在 x86_64 Linux 上编译。原生 macOS 不是受支持的构建主机；Mac
用户应使用 Linux 虚拟机、远程 Linux 服务器或自托管 Linux Runner。源码和构建目录
建议放在区分大小写的本地 NVMe 文件系统上。

| 编译机 | 建议并行度 | 使用体验 |
| --- | --- | --- |
| 4–8 核 / 16 GiB / 150 GiB 可用 SSD | `BB_NUMBER_THREADS=4`、`PARALLEL_MAKE=-j4` | 可以编译，但首次构建很慢 |
| 16 核 / 32 GiB / 250 GiB 可用 NVMe | `BB_NUMBER_THREADS=12`、`PARALLEL_MAKE=-j12` | 推荐配置，能持续利用大部分 CPU |
| 24–32 核 / 64–128 GiB / 300 GiB+ NVMe | 16–24 个并行任务 | 适合频繁全量构建和多人共享缓存 |

内存不足时不要把并行度直接设置为 CPU 线程数；LLVM、GCC、Rust 和 Node.js 的单个
任务会出现较高峰值内存。16 核 32 GiB 主机建议先从 12 个并行任务开始。高主频会改善
配方解析、链接和部分单线程任务，更多核心主要加速大量互相独立的 BitBake 任务。

## 7. GitHub Actions 编译

工作流位于
[.github/workflows/build-orangepi-zero2-image.yml](.github/workflows/build-orangepi-zero2-image.yml)，
使用 Ubuntu 24.04 Runner。进入仓库的 **Actions → Orange Pi Zero 2 OpenBMC → Run
workflow**：

- `preflight_only=false`：构建完整 `.wic`；
- `preflight_only=true`：只验证板级配方和代表性驱动对象，不生成镜像；
- `checkpoint=0`：正常从第一轮开始。

完整任务上限 360 分钟，其中 330 分钟为共享编译预算。下载目录、sstate 和哈希等价
数据库会缓存；正常预算到期且缓存成功时最多自动续编 5 轮。缓存以完成的 BitBake
任务为粒度，不能从被中断编译器进程的机器指令位置恢复。

成功任务上传：

- 可直接写卡的 `.wic`；
- `SHA256SUMS`；
- `.wic.verification.json`；
- 构建诊断日志。

## 8. 本地 Linux 编译 OpenBMC

以下示例适用于 Ubuntu 22.04/24.04 x86_64。先安装依赖：

```sh
sudo apt-get update
sudo apt-get install -y \
  bc bison build-essential chrpath cpio device-tree-compiler diffstat \
  e2fsprogs flex gawk gcc-aarch64-linux-gnu git libelf-dev liblz4-tool \
  libncurses-dev libssl-dev locales lz4 make mtools patch python3 \
  python3-git python3-jinja2 python3-pexpect python3-pip python3-setuptools \
  python3-subunit rsync socat texinfo u-boot-tools unzip wget xterm zstd
```

在干净检出中准备板级层：

```sh
cp -a meta-orangepi openbmc/meta-orangepi
cd openbmc
OPENBMC_SOURCE_DIR="$PWD"
OPENBMC_BUILD_DIR="$PWD/../openbmc-build"
TEMPLATECONF=meta-orangepi/conf/templates/default \
  . ./setup orangepi-zero2 "$OPENBMC_BUILD_DIR"
```

模板中包含历史共享集群路径。本地构建前必须修改
`$OPENBMC_BUILD_DIR/conf/local.conf`，至少覆盖这些值：

```conf
DL_DIR = "/absolute/path/yocto-downloads"
SSTATE_DIR = "/absolute/path/yocto-sstate"
TMPDIR = "/absolute/path/yocto-tmp"
BB_HASHSERVE_DB_DIR = "/absolute/path/yocto-sstate"

BB_NUMBER_THREADS = "12"
BB_NUMBER_PARSE_THREADS = "4"
PARALLEL_MAKE = "-j12"

PREMIRRORS = ""
PREMIRRORS:prepend = ""
MIRRORS = ""
CONNECTIVITY_CHECK_URIS = ""

OS_RELEASE_ROOTPATH = "/absolute/path/to/allwinnerbmc"
BBPATH:prepend = "/absolute/path/to/allwinnerbmc/openbmc/upstream-layers/openembedded-core/meta:"
HOSTTOOLS_NONFATAL:append = " chrpath rpcgen"
HOSTTOOLS:remove = " chrpath rpcgen"
```

随后初始化环境并构建：

```sh
cd "$OPENBMC_SOURCE_DIR"
. ./oe-init-build-env "$OPENBMC_BUILD_DIR"
bitbake obmc-phosphor-image
```

镜像位于 `$TMPDIR/deploy/images/orangepi-zero2/*.wic`。首次构建会下载并编译完整
交叉工具链；后续构建可复用 `DL_DIR` 和 `SSTATE_DIR`。

运行仓库测试和只读镜像检查：

```sh
python3 -m unittest discover -s tests -v
python3 scripts/verify-tf-image.py /path/to/image.wic
```

## 9. 编译 CH32V307 固件

需要 WCH CH32V307EVT 3.1 SDK 和包含 `riscv-none-embed-gcc` 的 WCH RISC-V 工具链。
macOS 默认路径匹配 MounRiver Studio 2；其他系统通过参数覆盖：

```sh
make -C firmware/ch32v307-kvm \
  WCH_EVT=/path/to/CH32V307EVT-3.1/EVT \
  TOOLCHAIN_DIR=/path/to/wch-riscv-toolchain/bin
```

输出位于：

```text
firmware/ch32v307-kvm/build/ch32v307-kvm.elf
firmware/ch32v307-kvm/build/ch32v307-kvm.hex
firmware/ch32v307-kvm/build/ch32v307-kvm.bin
```

固件烧入 CH32V307 后，P6 口连接被控主机；WCH-LinkE USB 口连接 OpenBMC。详细协议、
引脚和 Mac 调试 WebUI 见
[firmware/ch32v307-kvm/README.md](firmware/ch32v307-kvm/README.md)。

## 10. 烧录和校验

先校验镜像：

```sh
sha256sum -c SHA256SUMS
```

balenaEtcher 可以直接写入 `.wic`。Linux 高级用户也可以写入整张卡设备：

```sh
sudo dd if=obmc-phosphor-image-orangepi-zero2-20260831175858.wic \
  of=/dev/sdX bs=4M conv=fsync status=progress
```

`/dev/sdX` 必须是整张 TF 卡而不是分区。选择错误设备会不可恢复地覆盖数据。写卡后
建议断电重插，再通过串口观察 U-Boot 和 Linux 启动。

## 11. 当前限制

- 最新 Action 镜像已通过分区、SPL、U-Boot/BL31、启动文件、ext4、AArch64
  用户态和 WebUI 的只读检查，但验证报告明确标记 `hardware_boot_test: not performed`；
- 最新整卡镜像仍需分别在 512 MiB 与 1 GiB 板卡上完成重刷和全功能回归；
- MS2130 的最大分辨率、帧率和音频能力受具体采集卡版本与 USB 带宽影响；
- CH32V307 键鼠需要独立烧录 Release 中的 MCU 固件，并按 J2/USART1 接线；
- 不要把 GitHub Token、SSH 私钥或设备密码提交到仓库。

---

# English documentation

## 1. Project overview

This project targets both the 512 MiB and 1 GiB Orange Pi Zero 2. The two
boards use one machine configuration, device tree, and whole-card image; DRAM
size is detected by the boot firmware at runtime. The target SoC is the
Allwinner H616 with four Cortex-A53 ARMv8-A/AArch64 cores.

The repository provides:

- an `orangepi-zero2` Yocto/OpenBMC machine layer;
- pinned Linux 6.1, U-Boot 2021.10, and Trusted Firmware-A 2.14.2 sources;
- one directly flashable `.wic` TF-card image;
- an MS2130 USB HDMI capture path integrated with the OpenBMC WebUI KVM;
- WCH-LinkE discovery and CH32V307 composite USB keyboard/absolute-mouse
  firmware;
- a Simplified Chinese WebUI locale;
- resumable GitHub Actions builds, image-structure checks, and SHA-256 files.

Exact upstream repositories and commits are listed in
[sources/versions.txt](sources/versions.txt). Board metadata is in
`meta-orangepi/`, CH32V307 firmware is in `firmware/ch32v307-kvm/`, and the
vendored OpenBMC tree is in `openbmc/`.

## 2. System architecture

```text
                              Orange Pi Zero 2 / OpenBMC
┌──────────────┐   HTTPS   ┌───────────────────────────────┐
│ Browser UI   │◄─────────►│ bmcweb + webui-vue + noVNC   │
└──────┬───────┘           └──────────────┬────────────────┘
       │ browser input                    │ RFB / KVM
       │                                  ▼
       │                    ┌───────────────────────────────┐
       │                    │ obmc-ikvm                     │
       │                    │ video: V4L2 MJPEG             │
       │                    │ input: absolute pointer + key │
       │                    └──────────┬───────────▲────────┘
       │                               │           │
       │       921600-baud frames      │           │ MJPEG
       │                               ▼           │
       │                    ┌────────────────┐   ┌──┴───────────┐
       │                    │ WCH-LinkE CDC  │   │ MS2130 UVC   │◄── HDMI
       │                    │ /dev/ttyACM*   │   │ /dev/video0  │
       │                    └───────┬────────┘   └──────────────┘
       │                            │ USART1 PA9/PA10
       │                            ▼
       │                    ┌────────────────┐      P6 USB
       └───────────────────►│ CH32V307       │──────────────► managed host
                            │ key + abs mouse│                 USB HID
                            └────────────────┘
```

The TF card uses a conventional MBR layout:

- 8 KiB offset: `u-boot-sunxi-with-spl.bin`, containing SPL, U-Boot, and BL31;
- partition 1: FAT boot partition with the Linux `Image`, H616 device tree,
  `extlinux.conf`, and `uboot.env`;
- partition 2: ext4 OpenBMC root filesystem;
- `/dev/mmcblk0p2` is mounted directly, without an initramfs.

## 3. KVM video and absolute input

### Video path

The MS2130 is attached to the Orange Pi as a standard UVC/V4L2 device.
`uvcvideo` exposes `/dev/video0`; `obmc-ikvm` reads the negotiated MJPEG width,
height, and pixel format and feeds the existing WebUI KVM. Resolution is not
hard-coded to 1080p. A source resolution change reallocates the framebuffer
from the current V4L2 format. Available modes still depend on the particular
MS2130 firmware, HDMI source, and USB bandwidth.

### Coordinate path

The production UI uses one endpoint-exact absolute coordinate system:

```text
browser canvas coordinates
  -> noVNC converts back to MS2130 framebuffer coordinates
  -> obmc-ikvm clamps and maps each axis to 0..32767
  -> WCH-LinkE CDC serial frame
  -> CH32V307 P6 absolute USB HID mouse
  -> managed-host cursor
```

noVNC scales only the displayed canvas, does not resize the remote session,
and disables viewport dragging. `obmc-ikvm` uses a 64-bit intermediate and
rounding: the first framebuffer pixel maps exactly to `0`, the final pixel
maps exactly to `32767`, and out-of-range input is clamped. Browser size, CSS
scaling, and capture resolution therefore do not change the browser-to-host
pointer relationship.

The CH32V307 P6 device port exposes two HID interfaces to the managed host:

- Boot Keyboard with an 8-byte report;
- Absolute Mouse with a 6-byte `buttons, x_le16, y_le16, wheel` report.

The control link is USART1 at 921600 baud, 8-N-1:

```text
A5 5A | version | type | sequence | length | payload | crc16_le
```

CRC-16/CCITT-FALSE protects the frame. Packet types cover keyboard, pointer,
heartbeat, and release-all. The MCU releases every key and mouse button after
one second without link traffic.

### WCH-LinkE and CH32V307 wiring

Install the UART jumpers on the CH32V307V EVT J2 header:

- WCH-LinkE `RX_OUT` → CH32V307 `TX1` / PA9;
- WCH-LinkE `TX_OUT` → CH32V307 `RX1` / PA10;
- WCH-LinkE USB → Orange Pi Zero 2;
- CH32V307 P6 USB Device → managed host;
- UART signalling must be 3.3 V.

OpenBMC finds USB VID/PID `1a86:8010` and accepts only the matching `ttyACM*`
device, so it does not depend on a changing `/dev/ttyACM0` number. The daemon
periodically rediscovers the device after unplug/replug events.

## 4. Integrated hardware and drivers

| Area | Kernel/userspace components | Current status |
| --- | --- | --- |
| H616 CPU | ARM64, SMP, Cortex-A53, CPUFreq/OPP | Built; ondemand is the default governor |
| TF card | `MMC_SUNXI`, MBR, VFAT, ext4 | Built and checked by the image verifier |
| Clocks/platform | SUNXI CCU, H6 R-CCU, DE2 CCU, H616 pinctrl | Built |
| Thermal/watchdog/RTC | `SUN8I_THERMAL`, `SUNXI_WATCHDOG`, `RTC_DRV_SUN6I` | Built |
| Ethernet | STMMAC, `DWMAC_SUN8I`, AC200, Realtek/Motorcomm PHY | Drivers included |
| Onboard Wi-Fi | UWE5622, `sprdwl_ng`, cfg80211, rfkill, firmware, wpa_supplicant | Integrated; previously connected on hardware |
| USB host | xHCI, EHCI, OHCI, USB Storage, USB HID, USB Audio | Built |
| MS2130 video | `uvcvideo`, V4L2, MJPEG, `obmc-ikvm` | Integrated; previously hot-deployed on a 512 MiB board |
| WCH-LinkE | `cdc_acm`, VID/PID discovery, `ttyACM*` reconnect | Integrated; USART1 traffic verified with hardware breakpoints |
| CH32V307 HID | P6 composite keyboard/absolute mouse, heartbeat/failsafe | Firmware built, flashed, and enumerated by a host |
| GPIO | GPIO character device, libgpiod tools, board service | Integrated |
| Web management | bmcweb, webui-vue, noVNC, Simplified Chinese locale | Integrated |

“Built” or “integrated” means that the configuration, module, or package is
present in the build inputs and passed CI. It does not mean that the current
release has been regression-tested with every peripheral combination. The
latest whole-card image still needs complete boot, network, video, and input
testing on both 512 MiB and 1 GiB boards.

## 5. Latest release

Latest version:
[openbmc-orangepi-zero2-20260901-wchlinke-kvm](https://github.com/ZhengHaoRangay4hub/allwinnerbmc/releases/tag/openbmc-orangepi-zero2-20260901-wchlinke-kvm)

- OpenBMC image source commit: `3c9089d3d69afec13805aee44307eb6493ccdbd9`;
- build: [GitHub Actions #27](https://github.com/ZhengHaoRangay4hub/allwinnerbmc/actions/runs/33421854269);
- whole-card image: `obmc-phosphor-image-orangepi-zero2-20260831175858.wic`;
- image size: `336955392` bytes;
- image SHA-256: `fe57948c2166e590d26fd29fb69e9b52180bc24609d46acd2aebe7caa6dfc366`;
- CH32V307 BIN SHA-256: `19aec3e70e5c07ca958be0f2b348262b49720837bc6d1cbbd83072642de1c4d5`.

Release assets include the `.wic`, `SHA256SUMS`, image verification JSON, and
CH32V307 `.bin` and `.hex` files. The single `.wic` supports both RAM variants
and already contains Linux, the device tree, U-Boot, BL31, boot environment,
and the OpenBMC root filesystem.

## 6. Build-host requirements

Build OpenBMC/Yocto on x86_64 Linux. Native macOS is not a supported build
host; use a Linux VM, remote Linux server, or self-hosted Linux runner from a
Mac. Put source and build directories on a case-sensitive local NVMe filesystem.

| Build host | Suggested parallelism | Expected use |
| --- | --- | --- |
| 4–8 cores / 16 GiB / 150 GiB free SSD | `BB_NUMBER_THREADS=4`, `PARALLEL_MAKE=-j4` | Works, but a cold build is slow |
| 16 cores / 32 GiB / 250 GiB free NVMe | `BB_NUMBER_THREADS=12`, `PARALLEL_MAKE=-j12` | Recommended; sustains high CPU use |
| 24–32 cores / 64–128 GiB / 300 GiB+ NVMe | 16–24 parallel tasks | Frequent clean builds and shared caches |

Do not blindly match parallel jobs to hardware threads on a memory-limited
host. LLVM, GCC, Rust, and Node.js recipes can have high peak memory. Start a
16-core/32-GiB machine at 12 jobs. Higher clock speed helps parsing, linking,
and serial tasks; more cores help the many independent BitBake tasks.

## 7. GitHub Actions build

The workflow is
[.github/workflows/build-orangepi-zero2-image.yml](.github/workflows/build-orangepi-zero2-image.yml)
and runs on Ubuntu 24.04. Open **Actions → Orange Pi Zero 2 OpenBMC → Run
workflow**:

- `preflight_only=false`: build the complete `.wic`;
- `preflight_only=true`: validate board recipes and representative driver
  objects without producing an image;
- `checkpoint=0`: start a normal first run.

The job limit is 360 minutes, with a shared 330-minute compiler budget.
Downloads, sstate, and the hash-equivalence database are cached. A controlled
budget expiry can dispatch up to five continuation runs after saving cache.
Resume granularity is a completed BitBake task, not a machine-instruction
checkpoint inside an interrupted compiler.

A successful image job uploads:

- the directly flashable `.wic`;
- `SHA256SUMS`;
- `.wic.verification.json`;
- build diagnostics.

## 8. Local OpenBMC build on Linux

This example targets Ubuntu 22.04/24.04 x86_64. Install dependencies:

```sh
sudo apt-get update
sudo apt-get install -y \
  bc bison build-essential chrpath cpio device-tree-compiler diffstat \
  e2fsprogs flex gawk gcc-aarch64-linux-gnu git libelf-dev liblz4-tool \
  libncurses-dev libssl-dev locales lz4 make mtools patch python3 \
  python3-git python3-jinja2 python3-pexpect python3-pip python3-setuptools \
  python3-subunit rsync socat texinfo u-boot-tools unzip wget xterm zstd
```

Prepare the board layer in a clean checkout:

```sh
cp -a meta-orangepi openbmc/meta-orangepi
cd openbmc
OPENBMC_SOURCE_DIR="$PWD"
OPENBMC_BUILD_DIR="$PWD/../openbmc-build"
TEMPLATECONF=meta-orangepi/conf/templates/default \
  . ./setup orangepi-zero2 "$OPENBMC_BUILD_DIR"
```

The template contains historical shared-cluster paths. Before building,
override at least these values in `$OPENBMC_BUILD_DIR/conf/local.conf`:

```conf
DL_DIR = "/absolute/path/yocto-downloads"
SSTATE_DIR = "/absolute/path/yocto-sstate"
TMPDIR = "/absolute/path/yocto-tmp"
BB_HASHSERVE_DB_DIR = "/absolute/path/yocto-sstate"

BB_NUMBER_THREADS = "12"
BB_NUMBER_PARSE_THREADS = "4"
PARALLEL_MAKE = "-j12"

PREMIRRORS = ""
PREMIRRORS:prepend = ""
MIRRORS = ""
CONNECTIVITY_CHECK_URIS = ""

OS_RELEASE_ROOTPATH = "/absolute/path/to/allwinnerbmc"
BBPATH:prepend = "/absolute/path/to/allwinnerbmc/openbmc/upstream-layers/openembedded-core/meta:"
HOSTTOOLS_NONFATAL:append = " chrpath rpcgen"
HOSTTOOLS:remove = " chrpath rpcgen"
```

Initialize the environment and build:

```sh
cd "$OPENBMC_SOURCE_DIR"
. ./oe-init-build-env "$OPENBMC_BUILD_DIR"
bitbake obmc-phosphor-image
```

The image is under `$TMPDIR/deploy/images/orangepi-zero2/*.wic`. A cold build
downloads and compiles the full cross toolchain; later builds reuse `DL_DIR`
and `SSTATE_DIR`.

Run repository tests and the read-only image verifier with:

```sh
python3 -m unittest discover -s tests -v
python3 scripts/verify-tf-image.py /path/to/image.wic
```

## 9. Build the CH32V307 firmware

The firmware needs WCH CH32V307EVT 3.1 and a WCH RISC-V toolchain containing
`riscv-none-embed-gcc`. The default macOS path matches MounRiver Studio 2;
override both paths on other systems:

```sh
make -C firmware/ch32v307-kvm \
  WCH_EVT=/path/to/CH32V307EVT-3.1/EVT \
  TOOLCHAIN_DIR=/path/to/wch-riscv-toolchain/bin
```

Outputs are:

```text
firmware/ch32v307-kvm/build/ch32v307-kvm.elf
firmware/ch32v307-kvm/build/ch32v307-kvm.hex
firmware/ch32v307-kvm/build/ch32v307-kvm.bin
```

After flashing the MCU, connect P6 to the managed host and WCH-LinkE USB to
OpenBMC. Protocol, pin, and Mac test-UI details are in
[firmware/ch32v307-kvm/README.md](firmware/ch32v307-kvm/README.md).

## 10. Flashing and verification

Verify the download first:

```sh
sha256sum -c SHA256SUMS
```

balenaEtcher can write the `.wic` directly. Advanced Linux users may write the
entire card device:

```sh
sudo dd if=obmc-phosphor-image-orangepi-zero2-20260831175858.wic \
  of=/dev/sdX bs=4M conv=fsync status=progress
```

`/dev/sdX` must be the whole TF-card device, not a partition. A wrong target
will irreversibly overwrite data. Power-cycle/reinsert the card after writing
and monitor U-Boot and Linux through the serial console.

## 11. Current limitations

- The latest Action image passed read-only checks for partitions, SPL,
  U-Boot/BL31, boot files, ext4, AArch64 userspace, and WebUI, but its report
  explicitly says `hardware_boot_test: not performed`;
- the latest whole-card image still needs a fresh flash and full regression on
  both 512 MiB and 1 GiB boards;
- maximum MS2130 resolution, frame rate, and audio support depend on the exact
  capture-card firmware and USB bandwidth;
- CH32V307 input requires separately flashing the MCU asset from the Release
  and wiring J2/USART1 correctly;
- never commit GitHub tokens, SSH private keys, or device passwords.

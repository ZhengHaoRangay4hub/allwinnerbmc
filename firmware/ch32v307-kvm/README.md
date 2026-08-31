# CH32V307 OpenBMC KVM HID bridge

This firmware turns a CH32V307 into the USB keyboard and absolute-coordinate
mouse used by OpenBMC KVM. It is based on WCH's USBHS `CompositeKM` example and
uses the vendor USB device implementation from CH32V307EVT 3.1 at build time.

The target-facing USB port enumerates two HID interfaces:

- boot keyboard: 8-byte report;
- absolute mouse: 6-byte report (`buttons, x_le16, y_le16, wheel`).

The BMC-facing transport is USART2 at 921600 baud, 8-N-1. The default OpenBMC
connection uses a CH340 USB-to-UART adapter so the H616 side can discover the
bridge automatically:

```text
A5 5A | version | type | sequence | length | payload | crc16_le
```

CRC-16/CCITT-FALSE covers `version` through the end of `payload`. Packet types
are keyboard (`0x01`, 8 bytes), pointer (`0x02`, 6 bytes), heartbeat (`0x03`, no
payload), and release-all (`0x04`, no payload). If the link is silent for one
second, the firmware releases all keys and mouse buttons.

## Pins

- USART2 TX: PA2
- USART2 RX: PA3
- USBHS: the board's USBHS device connector/pins from the WCH CompositeKM
  example
- UART levels must be 3.3 V.

For the Orange Pi Zero 2 CH340 connection:

- H616 USB host -> CH340 USB
- CH340 TX -> CH32V307 PA3 / USART2 RX
- CH340 RX <- CH32V307 PA2 / USART2 TX
- CH340 GND <-> CH32V307 GND

The OpenBMC service matches the CH340/CH341 USB IDs and follows changes such as
`/dev/ttyUSB0` becoming `/dev/ttyUSB1`; no serial-port selection is required.

## Build

The default SDK path matches the local WCH installation. Override `WCH_EVT`
when needed:

```sh
make WCH_EVT=/path/to/CH32V307EVT-3.1/EVT
```

Outputs are written to `build/ch32v307-kvm.{elf,hex,bin}`.

---

# CH32V307 OpenBMC KVM 键鼠桥

该固件把 CH32V307 作为 OpenBMC KVM 的 USB 键盘和绝对坐标鼠标。面向被控
主机的一端枚举为键盘和鼠标两个 HID 接口；面向 BMC 的一端使用 USART2，
参数为 921600、8-N-1。

Orange Pi Zero 2 默认通过 CH340 连接，不需要在 Web UI 或配置文件中选择
`ttyUSB` 编号。OpenBMC 会根据 CH340/CH341 的 USB VID/PID 自动发现设备，
设备拔插或编号变化后也会自动重连。

## 接线

- H616 USB Host -> CH340 USB
- CH340 TX -> CH32V307 PA3 / USART2 RX
- CH340 RX <- CH32V307 PA2 / USART2 TX
- CH340 GND <-> CH32V307 GND
- CH32V307 USBHS Device -> 被控主机 USB

串口信号必须使用 3.3 V 电平，不要把 5 V TTL 信号直接接入 CH32V307。

## 编译

```sh
make WCH_EVT=/path/to/CH32V307EVT-3.1/EVT
```

编译结果位于 `build/ch32v307-kvm.{elf,hex,bin}`。通信静默超过一秒时，
固件会自动释放全部按键和鼠标按钮，避免断线后出现卡键。

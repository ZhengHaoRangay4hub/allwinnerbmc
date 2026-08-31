# CH32V307 OpenBMC KVM HID bridge

This firmware turns a CH32V307 into the USB keyboard and absolute-coordinate
mouse used by OpenBMC KVM. It is based on WCH's USBHS `CompositeKM` example and
uses the vendor USB device implementation from CH32V307EVT 3.1 at build time.

The target-facing USB port enumerates two HID interfaces:

- boot keyboard: 8-byte report;
- absolute mouse: 6-byte report (`buttons, x_le16, y_le16, wheel`).

The control transport is USART1 at 921600 baud, 8-N-1. On the CH32V307V EVT
board it is connected to the board's WCH-LinkE USB CDC port through the J2
SWD/UART jumpers:

```text
A5 5A | version | type | sequence | length | payload | crc16_le
```

CRC-16/CCITT-FALSE covers `version` through the end of `payload`. Packet types
are keyboard (`0x01`, 8 bytes), pointer (`0x02`, 6 bytes), heartbeat (`0x03`, no
payload), and release-all (`0x04`, no payload). If the link is silent for one
second, the firmware releases all keys and mouse buttons.

## Pins

- USART1 TX: PA9 (`TX1` on J2)
- USART1 RX: PA10 (`RX1` on J2)
- USBHS: the board's USBHS device connector/pins from the WCH CompositeKM
  example
- UART levels must be 3.3 V.

For the on-board WCH-LinkE connection, install the two J2 UART jumpers so that:

- WCH-LinkE `RX_OUT` is connected to target `TX1` / PA9
- WCH-LinkE `TX_OUT` is connected to target `RX1` / PA10
- the WCH-LinkE USB port is connected to the Mac or BMC host

The Mac WebUI under `webui/` matches the WCH-LinkE USB VID/PID automatically;
no serial-port selection is required.

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
主机的一端枚举为键盘和鼠标两个 HID 接口；控制通道使用 USART1，参数为
921600、8-N-1。

CH32V307V EVT 板上的 WCH-LinkE 通过 J2 的 SWD/UART 跳线连接到 USART1。
Mac WebUI 会根据 WCH-LinkE 的 USB VID/PID 自动发现控制串口，不需要手动
选择 `/dev/cu.usbmodem*` 编号。

## 接线

- J2 `RX_OUT` -> `TX1` / PA9 / USART1 TX
- J2 `TX_OUT` -> `RX1` / PA10 / USART1 RX
- WCH-LinkE USB -> Mac 或 BMC 控制端
- CH32V307 USBHS Device -> 被控主机 USB

串口信号必须使用 3.3 V 电平，不要把 5 V TTL 信号直接接入 CH32V307。

## 编译

```sh
make WCH_EVT=/path/to/CH32V307EVT-3.1/EVT
```

编译结果位于 `build/ch32v307-kvm.{elf,hex,bin}`。通信静默超过一秒时，
固件会自动释放全部按键和鼠标按钮，避免断线后出现卡键。

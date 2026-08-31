# Mac 局域网 KVM WebUI

该服务运行在 Mac 上，自动发现 WCH-Link 串口，并把浏览器里的虚拟键盘和
触控板动作转换成 CH32V307 KVM 协议。其他手机、平板或电脑可以通过 Mac
的局域网 IP 访问。

这里的触控板是固件联调工具，采用相对手势累积到 `0..32767` 的绝对 HID
坐标。OpenBMC 正式 WebUI 不使用该触控板算法；正式链路直接把 noVNC 视频
画布位置映射到 MS2130 视频帧，再端点精确地映射到同一个 `0..32767` 范围，
从而让网页鼠标位置与被控主机的实际鼠标位置一致。

## 启动

```sh
cd firmware/ch32v307-kvm/webui
python3 -m pip install -r requirements.txt
python3 server.py
```

启动后终端会显示带访问令牌的本机地址和局域网地址。把完整的局域网地址
发给需要控制的设备即可，例如：

```text
http://192.168.1.23:8765/?token=...
```

默认监听 `0.0.0.0:8765`，控制串口为自动发现的 WCH-Link USB modem，波特率
为 921600。需要覆盖时使用：

```sh
python3 server.py --serial /dev/cu.usbmodemD51F8F065A522 --baud 921600
```

只预览页面而不写串口：

```sh
python3 server.py --dry-run
```

页面失焦、关闭或点击“紧急释放”时，服务会发送 release-all，CH32V307 固件
本身还有 1 秒链路超时保护。

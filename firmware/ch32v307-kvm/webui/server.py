#!/usr/bin/env python3
"""LAN Web UI and WCH-Link serial controller for the CH32V307 KVM bridge."""

from __future__ import annotations

import argparse
import glob
import json
import os
import secrets
import socket
import struct
import subprocess
import threading
import time
from functools import partial
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

try:
    import serial
    from serial.tools import list_ports
except ImportError:  # Reported through /api/status so the UI still starts.
    serial = None
    list_ports = None


MAGIC = b"\xA5\x5A"
VERSION = 0x01
PACKET_KEYBOARD = 0x01
PACKET_POINTER = 0x02
PACKET_HEARTBEAT = 0x03
PACKET_RELEASE_ALL = 0x04
WCH_VID = 0x1A86
WCH_LINK_PID = 0x8010
STATIC_DIR = Path(__file__).resolve().parent / "static"


def crc16_ccitt_false(data: bytes) -> int:
    crc = 0xFFFF
    for value in data:
        crc ^= value << 8
        for _ in range(8):
            crc = ((crc << 1) ^ 0x1021) & 0xFFFF if crc & 0x8000 else (crc << 1) & 0xFFFF
    return crc


class SerialTransport:
    def __init__(self, device: str | None, baudrate: int, dry_run: bool = False) -> None:
        self.requested_device = device
        self.baudrate = baudrate
        self.dry_run = dry_run
        self._port = None
        self._device = None
        self._sequence = 0
        self._lock = threading.Lock()
        self.frames_sent = 0
        self.bytes_sent = 0
        self.last_frame_at = 0.0
        self.last_packet_type = None
        self.last_error = None

    def _candidate_devices(self) -> list[str]:
        if self.requested_device:
            return [self.requested_device]

        ranked: list[tuple[int, str]] = []
        if list_ports is not None:
            for port in list_ports.comports():
                score = 0
                if port.vid == WCH_VID and port.pid == WCH_LINK_PID:
                    score += 100
                if "wch" in f"{port.manufacturer} {port.product} {port.description}".lower():
                    score += 30
                if "usbmodem" in port.device:
                    score += 10
                ranked.append((score, port.device))

        for path in glob.glob("/dev/cu.usbmodem*"):
            if not any(item[1] == path for item in ranked):
                ranked.append((10, path))
        return [device for _, device in sorted(ranked, key=lambda item: (-item[0], item[1]))]

    def _close_locked(self) -> None:
        if self._port is not None:
            try:
                self._port.close()
            except Exception:
                pass
        self._port = None
        self._device = None

    def _ensure_open_locked(self) -> None:
        if self.dry_run:
            self.last_error = None
            return
        if serial is None:
            raise RuntimeError("缺少 pyserial，请运行 python3 -m pip install pyserial")
        if self._port is not None and self._port.is_open and self._device and os.path.exists(self._device):
            return

        self._close_locked()
        candidates = self._candidate_devices()
        if not candidates:
            raise RuntimeError("未发现 WCH-Link 串口（/dev/cu.usbmodem*）")

        errors = []
        for device in candidates:
            try:
                self._port = serial.Serial(
                    device,
                    self.baudrate,
                    timeout=0,
                    write_timeout=0.5,
                    rtscts=False,
                    dsrdtr=False,
                )
                self._device = device
                self.last_error = None
                return
            except Exception as exc:
                errors.append(f"{device}: {exc}")
        raise RuntimeError("；".join(errors))

    def probe(self) -> None:
        with self._lock:
            try:
                self._ensure_open_locked()
                self.last_error = None
            except Exception as exc:
                self.last_error = str(exc)
                self._close_locked()

    def send(self, packet_type: int, payload: bytes = b"") -> bytes:
        if len(payload) > 255:
            raise ValueError("payload too large")
        with self._lock:
            try:
                self._ensure_open_locked()
                body = bytes((VERSION, packet_type, self._sequence, len(payload))) + payload
                frame = MAGIC + body + struct.pack("<H", crc16_ccitt_false(body))
                self._sequence = (self._sequence + 1) & 0xFF
                if not self.dry_run:
                    self._port.write(frame)
                    self._port.flush()
                self.frames_sent += 1
                self.bytes_sent += len(frame)
                self.last_frame_at = time.time()
                self.last_packet_type = packet_type
                self.last_error = None
                return frame
            except Exception as exc:
                self.last_error = str(exc)
                self._close_locked()
                raise

    def snapshot(self) -> dict:
        self.probe()
        with self._lock:
            return {
                "mode": "dry-run" if self.dry_run else "serial",
                "connected": self.dry_run or bool(self._port is not None and self._port.is_open),
                "device": self._device or self.requested_device,
                "baudrate": self.baudrate,
                "framesSent": self.frames_sent,
                "bytesSent": self.bytes_sent,
                "lastFrameAt": self.last_frame_at or None,
                "lastPacketType": self.last_packet_type,
                "lastError": self.last_error,
            }


class HidProbe:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._updated_at = 0.0
        self._cached = {"device": False, "keyboard": False, "mouse": False, "error": None}

    def snapshot(self) -> dict:
        with self._lock:
            if time.monotonic() - self._updated_at < 2.0:
                return dict(self._cached)
            try:
                result = subprocess.run(
                    ["ioreg", "-p", "IOUSB", "-l", "-w", "0"],
                    check=True,
                    capture_output=True,
                    text=True,
                    timeout=2,
                )
                present = "CH32V307 KVM HID" in result.stdout or "OBMCKVM1" in result.stdout
                keyboard = False
                mouse = False
                if present:
                    hid = subprocess.run(
                        ["hidutil", "list"],
                        check=False,
                        capture_output=True,
                        text=True,
                        timeout=2,
                    ).stdout
                    matching = [line.lower() for line in hid.splitlines() if "1a86" in line.lower() and "fe10" in line.lower()]
                    keyboard = any("keyboard" in line or "0x6" in line for line in matching)
                    mouse = any("mouse" in line or "0x2" in line for line in matching)
                    if matching and not (keyboard or mouse):
                        keyboard = mouse = True
                self._cached = {
                    "device": present,
                    "keyboard": keyboard,
                    "mouse": mouse,
                    "error": None,
                }
            except Exception as exc:
                self._cached = {"device": False, "keyboard": False, "mouse": False, "error": str(exc)}
            self._updated_at = time.monotonic()
            return dict(self._cached)


class KvmController:
    def __init__(self, transport: SerialTransport) -> None:
        self.transport = transport
        self.hid_probe = HidProbe()
        self.started_at = time.time()
        self.last_action = "等待控制"

    @staticmethod
    def _integer(value, low: int, high: int, name: str) -> int:
        if isinstance(value, bool) or not isinstance(value, int) or not low <= value <= high:
            raise ValueError(f"{name} 必须是 {low} 到 {high} 的整数")
        return value

    def keyboard(self, body: dict) -> None:
        modifiers = self._integer(body.get("modifiers", 0), 0, 255, "modifiers")
        keys = body.get("keys", [])
        if not isinstance(keys, list) or len(keys) > 6:
            raise ValueError("keys 必须是最多 6 个 HID usage")
        usages = [self._integer(value, 0, 255, "key usage") for value in keys]
        payload = bytes((modifiers, 0, *usages, *([0] * (6 - len(usages)))))
        self.transport.send(PACKET_KEYBOARD, payload)
        self.last_action = "键盘报告已写入"

    def pointer(self, body: dict) -> None:
        buttons = self._integer(body.get("buttons", 0), 0, 7, "buttons")
        x = self._integer(body.get("x", 16384), 0, 32767, "x")
        y = self._integer(body.get("y", 16384), 0, 32767, "y")
        wheel = self._integer(body.get("wheel", 0), -127, 127, "wheel")
        payload = bytes((buttons, x & 0xFF, x >> 8, y & 0xFF, y >> 8, wheel & 0xFF))
        self.transport.send(PACKET_POINTER, payload)
        self.last_action = "鼠标报告已写入"

    def heartbeat(self) -> None:
        self.transport.send(PACKET_HEARTBEAT)

    def release_all(self) -> None:
        self.transport.send(PACKET_RELEASE_ALL)
        self.last_action = "全部按键与鼠标按钮已释放"

    def status(self) -> dict:
        return {
            "ok": True,
            "server": {"startedAt": self.started_at, "uptime": int(time.time() - self.started_at)},
            "serial": self.transport.snapshot(),
            "hid": self.hid_probe.snapshot(),
            "lastAction": self.last_action,
        }


class KvmRequestHandler(SimpleHTTPRequestHandler):
    controller: KvmController
    access_token: str

    def log_message(self, fmt: str, *args) -> None:
        print(f"[{self.log_date_time_string()}] {self.address_string()} {fmt % args}")

    def end_headers(self) -> None:
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def _authorized(self) -> bool:
        parsed = urlparse(self.path)
        query_token = parse_qs(parsed.query).get("token", [None])[0]
        header_token = self.headers.get("X-KVM-Token")
        auth = self.headers.get("Authorization", "")
        bearer_token = auth[7:] if auth.startswith("Bearer ") else None
        supplied = header_token or bearer_token or query_token
        return bool(supplied and secrets.compare_digest(supplied, self.access_token))

    def _json(self, status: int, payload: dict) -> None:
        encoded = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def _require_api_auth(self) -> bool:
        if self._authorized():
            return True
        self._json(HTTPStatus.UNAUTHORIZED, {"ok": False, "error": "访问令牌无效"})
        return False

    def _read_json(self) -> dict:
        length = int(self.headers.get("Content-Length", "0"))
        if length > 16384:
            raise ValueError("请求体过大")
        data = self.rfile.read(length)
        value = json.loads(data or b"{}")
        if not isinstance(value, dict):
            raise ValueError("请求体必须是 JSON object")
        return value

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/api/status":
            if self._require_api_auth():
                self._json(HTTPStatus.OK, self.controller.status())
            return
        if parsed.path == "/healthz":
            self._json(HTTPStatus.OK, {"ok": True})
            return
        self.path = parsed.path
        super().do_GET()

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        if not parsed.path.startswith("/api/"):
            self._json(HTTPStatus.NOT_FOUND, {"ok": False, "error": "接口不存在"})
            return
        if not self._require_api_auth():
            return
        try:
            body = self._read_json()
            if parsed.path == "/api/keyboard":
                self.controller.keyboard(body)
            elif parsed.path == "/api/pointer":
                self.controller.pointer(body)
            elif parsed.path == "/api/heartbeat":
                self.controller.heartbeat()
            elif parsed.path == "/api/release":
                self.controller.release_all()
            else:
                self._json(HTTPStatus.NOT_FOUND, {"ok": False, "error": "接口不存在"})
                return
            self._json(HTTPStatus.OK, {"ok": True})
        except (ValueError, json.JSONDecodeError) as exc:
            self._json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": str(exc)})
        except Exception as exc:
            self._json(HTTPStatus.SERVICE_UNAVAILABLE, {"ok": False, "error": str(exc)})


def lan_addresses(port: int, token: str) -> list[str]:
    addresses = set()
    try:
        output = subprocess.run(
            ["ifconfig"], check=True, capture_output=True, text=True, timeout=2
        ).stdout
        for line in output.splitlines():
            line = line.strip()
            if line.startswith("inet "):
                address = line.split()[1]
                if not address.startswith(("127.", "169.254.")):
                    addresses.add(address)
    except Exception:
        try:
            addresses.add(socket.gethostbyname(socket.gethostname()))
        except OSError:
            pass
    return [f"http://{address}:{port}/?token={token}" for address in sorted(addresses)]


def main() -> None:
    parser = argparse.ArgumentParser(description="CH32V307 KVM LAN Web UI")
    parser.add_argument("--bind", default="0.0.0.0", help="监听地址，默认 0.0.0.0")
    parser.add_argument("--port", type=int, default=8765, help="监听端口，默认 8765")
    parser.add_argument("--serial", dest="serial_device", help="指定 WCH-Link 串口设备")
    parser.add_argument("--baud", type=int, default=921600, help="串口波特率")
    parser.add_argument("--token", default=os.environ.get("KVM_WEB_TOKEN"), help="WebUI 访问令牌")
    parser.add_argument("--dry-run", action="store_true", help="不写串口，仅用于界面测试")
    args = parser.parse_args()

    token = args.token or secrets.token_urlsafe(18)
    transport = SerialTransport(args.serial_device, args.baud, args.dry_run)
    controller = KvmController(transport)
    KvmRequestHandler.controller = controller
    KvmRequestHandler.access_token = token
    handler = partial(KvmRequestHandler, directory=str(STATIC_DIR))

    server = ThreadingHTTPServer((args.bind, args.port), handler)
    print("\nCH32V307 KVM WebUI 已启动")
    print(f"本机地址: http://127.0.0.1:{args.port}/?token={token}")
    for url in lan_addresses(args.port, token):
        print(f"局域网地址: {url}")
    print("按 Ctrl+C 停止。\n", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        try:
            controller.release_all()
        except Exception:
            pass
        server.server_close()


if __name__ == "__main__":
    main()

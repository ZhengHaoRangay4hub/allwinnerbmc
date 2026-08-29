#!/usr/bin/env python3
"""Read-only structure/content checks for the H616 TF-card image.

Requires mtools (mcopy), dtc (fdtget), and e2fsprogs (debugfs/e2fsck).
This does not emulate the board or replace a physical boot test.
"""
import argparse
import gzip
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import struct
import subprocess
import sys
import tempfile
import zlib


class InvalidImage(Exception):
    pass


def require(condition, message):
    if not condition:
        raise InvalidImage(message)


def read_at(stream, offset, size):
    stream.seek(offset)
    data = stream.read(size)
    require(len(data) == size, f"Truncated image at byte {offset}")
    return data


def partitions(mbr, image_size):
    require(len(mbr) == 512 and mbr[510:512] == b"\x55\xaa", "Invalid MBR signature")
    require(image_size % 512 == 0, "Image length is not sector-aligned")
    result = []
    for index in range(4):
        entry = mbr[446 + index * 16:462 + index * 16]
        if index >= 2:
            require(entry == bytes(16), "Expected exactly two MBR partitions")
            continue
        start, sectors = struct.unpack_from("<II", entry, 8)
        require(sectors > 0 and start > 0, f"Partition {index + 1} is empty")
        require((start + sectors) * 512 <= image_size,
                f"Partition {index + 1} extends beyond the image")
        result.append({"offset": start * 512, "size": sectors * 512,
                       "type": entry[4], "active": entry[0]})
    boot, root = result
    require(boot["active"] == 0x80 and root["active"] == 0,
            "Only the FAT boot partition must be marked active")
    require(boot["type"] in (0x06, 0x0B, 0x0C, 0x0E), "Partition 1 is not FAT")
    require(root["type"] == 0x83, "Partition 2 is not a Linux filesystem")
    require(boot["offset"] >= 1024 * 1024, "Boot partition overlaps the sunxi boot area")
    require(boot["offset"] + boot["size"] <= root["offset"], "Partitions overlap")
    return result


def spl_and_fit(boot_area):
    spl = boot_area[8192:]
    require(len(spl) >= 96 and spl[4:12] == b"eGON.BT0",
            "No Allwinner eGON SPL header at the 8 KiB boot offset")
    require(struct.unpack_from("<I", spl)[0] & 0xFF000000 == 0xEA000000,
            "Invalid SPL entry instruction")
    checksum, length = struct.unpack_from("<II", spl, 12)
    require(96 <= length <= len(spl) and length % 512 == 0,
            "Invalid or truncated SPL length")
    words = struct.iter_unpack("<I", spl[:length])
    computed = (sum(word[0] for word in words) - checksum + 0x5F0A6C39) & 0xFFFFFFFF
    require(computed == checksum, "SPL checksum mismatch")
    require(spl[20:23] == b"SPL", "Missing sunxi SPL signature")
    fit = spl[length:]
    require(len(fit) >= 40 and fit[:4] == b"\xd0\x0d\xfe\xed",
            "No U-Boot FIT immediately after SPL")
    fit_size = struct.unpack_from(">I", fit, 4)[0]
    require(40 <= fit_size <= len(fit), "Invalid or truncated U-Boot FIT")
    return fit[:fit_size], length


def command(*args):
    result = subprocess.run([str(arg) for arg in args], stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE, timeout=300,
                            env={**os.environ, "LC_ALL": "C"})
    require(result.returncode == 0,
            f"{args[0]} failed: {result.stderr.decode(errors='replace')[-2000:]}")
    return result.stdout


def fdt_property(path, node, prop, kind="s"):
    return command("fdtget", "-t", kind, path, node, prop).decode().strip()


def check_card_detect(path, label):
    node = "/soc/mmc@4020000"
    properties = command("fdtget", "-p", path, node).decode().split()
    require("cd-gpios" not in properties,
            f"{label} DTB still depends on the PF6 card-detect GPIO")
    require("broken-cd" in properties,
            f"{label} DTB is missing broken-cd for TF-card probing")


def check_fit(path):
    config = fdt_property(path, "/configurations", "default")
    require(re.fullmatch(r"[A-Za-z0-9_,.+@-]+", config), "Invalid default FIT configuration")
    config_path = "/configurations/" + config
    require(fdt_property(path, config_path, "firmware") == "atf",
            "SPL must enter BL31 before U-Boot")
    require("uboot" in fdt_property(path, config_path, "loadables").split(),
            "Default FIT configuration does not load U-Boot")
    payloads = {}
    for node in ("atf", "uboot"):
        prefix = "/images/" + node
        require(fdt_property(path, prefix, "arch") == "arm64",
                f"{node} is not AArch64 firmware")
        require(fdt_property(path, prefix, "compression") == "none",
                f"Unexpected compression for {node}")
        # This pinned sunxi binman configuration stores inline FIT data.
        payload = bytes(int(value, 16) for value in
                        fdt_property(path, prefix, "data", "bx").split())
        require(len(payload) >= 1024 and any(payload), f"{node} payload is missing/empty")
        payloads[node] = {"size": len(payload), "sha256": hashlib.sha256(payload).hexdigest()}
    for prop in ("load", "entry"):
        require(int(fdt_property(path, "/images/atf", prop, "x"), 16) == 0x40000000,
                f"BL31 {prop} address does not match H616")
    fdt_node = fdt_property(path, config_path, "fdt")
    fdt_path = "/images/" + fdt_node
    require(fdt_property(path, fdt_path, "type") == "flat_dt",
            "Default FIT configuration lacks a device tree")
    tree = bytes(int(value, 16) for value in
                 fdt_property(path, fdt_path, "data", "bx").split())
    require(len(tree) >= 40 and tree[:4] == b"\xd0\x0d\xfe\xed" and
            40 <= struct.unpack_from(">I", tree, 4)[0] <= len(tree),
            "Default FIT device tree is missing or truncated")
    tree_path = path.with_name("u-boot-control.dtb")
    tree_path.write_bytes(tree)
    check_card_detect(tree_path, "U-Boot control")
    return payloads


def check_extlinux(text):
    settings = {}
    for line in text.splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            fields = line.split(None, 1)
            settings[fields[0].upper()] = fields[1] if len(fields) > 1 else ""
    require(settings.get("DEFAULT") == "openbmc" and settings.get("LABEL") == "openbmc",
            "Unexpected extlinux boot entry")
    require(settings.get("KERNEL") == "/Image", "extlinux kernel path is wrong")
    require(settings.get("FDT") == "/sun50i-h616-orangepi-zero2.dtb",
            "extlinux device tree path is wrong")
    args = settings.get("APPEND", "").split()
    for value in ("root=/dev/mmcblk0p2", "rootfstype=ext4", "rootwait",
                  "console=ttyS0,115200n8"):
        require(value in args, f"Missing kernel argument: {value}")
    require([arg for arg in args if arg.startswith("root=")] == ["root=/dev/mmcblk0p2"],
            "Conflicting kernel root arguments")


def check_aarch64(data, name):
    require(len(data) >= 64 and data[:6] == b"\x7fELF\x02\x01",
            f"{name} is not a little-endian 64-bit ELF executable")
    require(struct.unpack_from("<H", data, 18)[0] == 183, f"{name} is not AArch64")


def check_environment(data):
    require(len(data) == 0x20000, "Incorrect U-Boot environment size")
    require(struct.unpack_from("<I", data)[0] == zlib.crc32(data[4:]),
            "U-Boot environment CRC mismatch")
    require(b"\0\0" in data[4:], "U-Boot environment is unterminated")
    entries = data[4:].split(b"\0\0", 1)[0].split(b"\0")
    variables = dict(entry.split(b"=", 1) for entry in entries if b"=" in entry)
    require(variables.get(b"bootcmd"), "Default boot command is missing")
    require(b"mmc0" in variables.get(b"boot_targets", b"").split(),
            "Default environment does not scan the TF card")
    return variables[b"bootcmd"].decode()


def check_wifi_support(path):
    listing = command("debugfs", "-R", "ls -p /lib/modules", path).decode()
    versions = re.findall(r"/\d+/04\d+/\d+/\d+/([^/]+)/", listing)
    versions = [name for name in versions if name not in (".", "..")]
    require(len(versions) == 1, "Expected exactly one installed kernel module tree")
    modules_dir = f"/lib/modules/{versions[0]}"
    dependencies = command(
        "debugfs", "-R", f"cat {modules_dir}/modules.dep", path
    ).decode()
    for module in ("uwe5622_bsp_sdio", "sprdwl_ng", "cfg80211", "rfkill"):
        match = re.search(
            rf"(?m)^([^:]*\b{re.escape(module)}\.ko(?:\.[a-z0-9]+)?):",
            dependencies,
        )
        require(match, f"Wi-Fi kernel module is absent: {module}")
        metadata = command(
            "debugfs", "-R", f"stat {modules_dir}/{match.group(1)}", path
        ).decode()
        require("Type: regular" in metadata, f"Wi-Fi module file is absent: {module}")

    firmware = command("debugfs", "-R", "cat /lib/firmware/wcnmodem.bin", path)
    require(len(firmware) > 900_000 and any(firmware), "UWE5622 firmware is absent/truncated")
    board_config = command(
        "debugfs", "-R", "cat /lib/firmware/wifi_2355b001_1ant.ini", path
    )
    require(b"Major =" in board_config and b"Calib_Bypass =" in board_config,
            "UWE5622 board calibration is absent/invalid")

    service = command(
        "debugfs", "-R", "cat /usr/lib/systemd/system/orangepi-wifi.service", path
    )
    require(b"modprobe uwe5622_bsp_sdio" in service and
            b"modprobe sprdwl_ng" in service and b"wpa_supplicant" in service,
            "Orange Pi Wi-Fi startup service is incomplete")
    network = command(
        "debugfs", "-R", "cat /usr/lib/systemd/network/80-wlan0.network", path
    )
    require(b"Name=wlan0" in network and b"DHCP=yes" in network,
            "wlan0 networkd configuration is absent")
    config = command(
        "debugfs", "-R", "cat /etc/wpa_supplicant/wpa_supplicant-wlan0.conf", path
    )
    require(b"ctrl_interface=/run/wpa_supplicant" in config,
            "wlan0 wpa_supplicant configuration is absent")
    for binary in ("/usr/sbin/iw", "/usr/sbin/wpa_supplicant", "/usr/sbin/rfkill"):
        check_aarch64(command("debugfs", "-R", "cat " + binary, path), binary)


def extract_region(stream, offset, size, output):
    """Copy only the chosen partition; sparse output avoids duplicating zeroes."""
    stream.seek(offset)
    with output.open("wb") as target:
        remaining = size
        while remaining:
            block = stream.read(min(1024 * 1024, remaining))
            require(block, "Image truncated while extracting a partition")
            if block.count(0) == len(block):
                target.seek(len(block), 1)
            else:
                target.write(block)
            remaining -= len(block)
        target.truncate(size)


def check_rootfs(path, expected_bootcmd=None):
    command("e2fsck", "-f", "-n", path)
    # debugfs may exit zero for a missing file, so validate returned content.
    release = command("debugfs", "-R", "cat /usr/lib/os-release", path).decode()
    require(re.search(r"(?im)^ID=.*openbmc", release), "Root filesystem is not OpenBMC")
    for binary in ("/usr/lib/systemd/systemd", "/usr/bin/bmcweb", "/usr/bin/fw_printenv"):
        check_aarch64(command("debugfs", "-R", "cat " + binary, path), binary)
    init = command("debugfs", "-R", "stat /sbin/init", path).decode()
    require("Type: symlink" in init and "systemd/systemd" in init,
            "The init link does not select systemd")
    service = command("debugfs", "-R", "cat /usr/lib/systemd/system/bmcweb.service", path)
    require(b"[Service]" in service and b"bmcweb" in service, "bmcweb service is absent")
    webui = command("debugfs", "-R", "cat /usr/share/www/index.html", path)
    if not webui:
        compressed = command("debugfs", "-R", "cat /usr/share/www/index.html.gz", path)
        require(compressed, "OpenBMC Web UI is absent")
        webui = gzip.decompress(compressed)
    require(b"<html" in webui.lower(), "OpenBMC Web UI index is not HTML")
    config = command("debugfs", "-R", "cat /etc/fw_env.config", path).decode()
    entries = [line.split() for line in config.splitlines()
               if line.strip() and not line.lstrip().startswith("#")]
    require(len(entries) == 1 and entries[0] == ["/boot/uboot.env", "0x0", "0x20000"],
            "fw_env.config does not describe the TF card's environment file")
    env_text = command("debugfs", "-R", "cat /etc/u-boot-initial-env", path).decode()
    variables = dict(line.split("=", 1) for line in env_text.splitlines() if "=" in line)
    require(variables.get("bootcmd"), "Fallback U-Boot environment is absent")
    if expected_bootcmd is not None:
        require(variables["bootcmd"] == expected_bootcmd, "Fallback boot command differs from FAT environment")
    setter = command("debugfs", "-R", "stat /usr/bin/fw_setenv", path).decode()
    require("Type: symlink" in setter and "fw_printenv" in setter, "fw_setenv utility is absent")
    check_wifi_support(path)
    return release.strip()


def verify(image):
    require(image.is_file(), f"Not a regular image file: {image}")
    for tool in ("mcopy", "fdtget", "debugfs", "e2fsck"):
        require(shutil.which(tool), f"Missing verification tool: {tool}")
    image_size = image.stat().st_size
    with image.open("rb") as stream, tempfile.TemporaryDirectory(prefix="opizero-wic-") as name:
        temp = Path(name)
        boot, root = partitions(read_at(stream, 0, 512), image_size)
        require(boot["offset"] <= 16 * 1024 * 1024, "Unexpectedly large pre-partition boot area")
        fit, spl_size = spl_and_fit(read_at(stream, 0, boot["offset"]))
        fit_path = temp / "u-boot.fit"
        fit_path.write_bytes(fit)
        payloads = check_fit(fit_path)
        for source, target in (("/Image", "Image"),
                               ("/sun50i-h616-orangepi-zero2.dtb", "board.dtb"),
                               ("/extlinux/extlinux.conf", "extlinux.conf"),
                               ("/uboot.env", "uboot.env")):
            command("mcopy", "-i", f"{image}@@{boot['offset']}", "::" + source, temp / target)
        with (temp / "Image").open("rb") as kernel:
            header = kernel.read(64)
        require(len(header) == 64 and header[56:60] == b"ARM\x64", "Invalid ARM64 Linux Image")
        compatible = fdt_property(temp / "board.dtb", "/", "compatible").split()
        require("xunlong,orangepi-zero2" in compatible and "allwinner,sun50i-h616" in compatible,
                "Boot partition contains the wrong board's DTB")
        check_card_detect(temp / "board.dtb", "Kernel")
        check_extlinux((temp / "extlinux.conf").read_text())
        bootcmd = check_environment((temp / "uboot.env").read_bytes())
        superblock = read_at(stream, root["offset"] + 1024, 1024)
        require(superblock[56:58] == b"\x53\xef", "Root partition lacks an ext filesystem")
        require(superblock[120:136].rstrip(b"\0") == b"root", "Unexpected root volume label")
        root_path = temp / "root.ext4"
        extract_region(stream, root["offset"], root["size"], root_path)
        release = check_rootfs(root_path, bootcmd)
    with image.open("rb") as stream:
        digest = hashlib.file_digest(stream, "sha256").hexdigest()
    return {"image": image.name, "size": image_size, "sha256": digest,
            "partitions": [boot, root], "spl_size": spl_size, "firmware": payloads,
            "os_release": release, "hardware_boot_test": "not performed"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("image", type=Path)
    args = parser.parse_args()
    try:
        print(json.dumps(verify(args.image.resolve()), indent=2))
    except (InvalidImage, OSError, ValueError, subprocess.SubprocessError) as error:
        print(f"IMAGE CHECK FAILED: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

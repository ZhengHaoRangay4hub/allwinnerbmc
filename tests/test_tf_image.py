"""Image-structure regression tests; fixtures are deliberately not bootable."""
import importlib.util
import io
import gzip
import os
from pathlib import Path
import shutil
import struct
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("verify_tf_image", ROOT / "scripts/verify-tf-image.py")
VERIFY = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(VERIFY)


def mbr_fixture():
    data = bytearray(512)
    data[510:] = b"\x55\xaa"
    data[446], data[450] = 0x80, 0x0C
    struct.pack_into("<II", data, 454, 2048, 131072)
    data[466] = 0x83
    struct.pack_into("<II", data, 470, 139264, 65536)
    return data


def boot_fixture():
    area = bytearray(1024 * 1024)
    spl = bytearray(32768)
    struct.pack_into("<I", spl, 0, 0xEA000016)
    spl[4:12] = b"eGON.BT0"
    struct.pack_into("<II", spl, 12, 0x5F0A6C39, len(spl))
    spl[20:24] = b"SPL\x02"
    checksum = sum(int.from_bytes(spl[i:i + 4], "little")
                   for i in range(0, len(spl), 4)) & 0xFFFFFFFF
    struct.pack_into("<I", spl, 12, checksum)
    area[8192:8192 + len(spl)] = spl
    struct.pack_into(">II", area, 8192 + len(spl), 0xD00DFEED, 40)
    return area


class ImageStructureTest(unittest.TestCase):
    def test_expected_two_partition_layout(self):
        boot, root = VERIFY.partitions(mbr_fixture(), 204800 * 512)
        self.assertEqual(boot["offset"], 1024 * 1024)
        self.assertEqual(root["type"], 0x83)

    def test_reject_missing_mbr(self):
        with self.assertRaisesRegex(VERIFY.InvalidImage, "MBR signature"):
            VERIFY.partitions(bytes(512), 204800 * 512)

    def test_reject_truncated_partition(self):
        with self.assertRaisesRegex(VERIFY.InvalidImage, "beyond"):
            VERIFY.partitions(mbr_fixture(), 204799 * 512)

    def test_reject_overlapping_partitions(self):
        mbr = mbr_fixture()
        struct.pack_into("<I", mbr, 470, 4096)
        with self.assertRaisesRegex(VERIFY.InvalidImage, "overlap"):
            VERIFY.partitions(mbr, 204800 * 512)

    def test_reject_missing_root_partition(self):
        mbr = mbr_fixture()
        mbr[462:478] = bytes(16)
        with self.assertRaisesRegex(VERIFY.InvalidImage, "empty"):
            VERIFY.partitions(mbr, 204800 * 512)

    def test_valid_spl_checksum_and_fit_location(self):
        fit, size = VERIFY.spl_and_fit(boot_fixture())
        self.assertEqual(size, 32768)
        self.assertEqual(fit[:4], b"\xd0\x0d\xfe\xed")

    def test_corrupt_spl_is_rejected(self):
        area = boot_fixture()
        area[8192 + 128] = 1
        with self.assertRaisesRegex(VERIFY.InvalidImage, "checksum"):
            VERIFY.spl_and_fit(area)

    def test_missing_fit_is_rejected(self):
        area = boot_fixture()
        area[8192 + 32768] = 0
        with self.assertRaisesRegex(VERIFY.InvalidImage, "No U-Boot FIT"):
            VERIFY.spl_and_fit(area)

    def test_truncated_fit_is_rejected(self):
        area = boot_fixture()
        struct.pack_into(">I", area, 8192 + 32768 + 4, len(area))
        with self.assertRaisesRegex(VERIFY.InvalidImage, "truncated U-Boot FIT"):
            VERIFY.spl_and_fit(area)

    def test_spl_at_wrong_device_offset_is_rejected(self):
        area = bytes(8192) + boot_fixture()[:-8192]
        with self.assertRaisesRegex(VERIFY.InvalidImage, "8 KiB"):
            VERIFY.spl_and_fit(area)

    def test_extlinux_has_directly_resolvable_root(self):
        config = (ROOT / "meta-orangepi/recipes-bsp/boot/orangepi-boot-files/"
                  "orangepi-zero2-extlinux.conf").read_text()
        VERIFY.check_extlinux(config)
        with self.assertRaisesRegex(VERIFY.InvalidImage, "root="):
            VERIFY.check_extlinux(config.replace("root=/dev/mmcblk0p2", "root=LABEL=root"))

    def test_conflicting_root_argument_is_rejected(self):
        config = (ROOT / "meta-orangepi/recipes-bsp/boot/orangepi-boot-files/"
                  "orangepi-zero2-extlinux.conf").read_text()
        with self.assertRaisesRegex(VERIFY.InvalidImage, "Conflicting"):
            VERIFY.check_extlinux(config.rstrip() + " root=/dev/mmcblk1p2\n")

    def test_reject_wrong_elf_architecture(self):
        elf = bytearray(64)
        elf[:6] = b"\x7fELF\x02\x01"
        struct.pack_into("<H", elf, 18, 183)
        VERIFY.check_aarch64(elf, "fixture")
        struct.pack_into("<H", elf, 18, 62)
        with self.assertRaisesRegex(VERIFY.InvalidImage, "not AArch64"):
            VERIFY.check_aarch64(elf, "fixture")

    def test_partition_extraction_is_exact_and_source_readonly(self):
        original = b"prefix" + bytes(1024 * 1024) + b"data" + b"suffix"
        source = io.BytesIO(original)
        with tempfile.TemporaryDirectory(prefix="opizero-test-") as directory:
            output = Path(directory) / "partition"
            VERIFY.extract_region(source, 6, 1024 * 1024 + 4, output)
            self.assertEqual(output.read_bytes(), original[6:-6])
        self.assertEqual(source.getvalue(), original)


class ImageFilesystemTest(unittest.TestCase):
    """Exercise real FAT/ext4/FDT tooling with explicitly non-bootable fixtures."""

    @classmethod
    def setUpClass(cls):
        required = ("mformat", "mcopy", "mmd", "dtc", "fdtget",
                    "mkfs.ext4", "debugfs", "e2fsck")
        missing = [tool for tool in required if not shutil.which(tool)]
        if missing:
            message = "Missing filesystem test tools: " + ", ".join(missing)
            if os.environ.get("OPENBMC_REQUIRE_IMAGE_TOOLS") == "1":
                raise RuntimeError(message)
            raise unittest.SkipTest(message)
        cls.temp = tempfile.TemporaryDirectory(prefix="opizero-fs-test-")
        cls.addClassCleanup(cls.temp.cleanup)
        cls.directory = Path(cls.temp.name)
        cls.rootdir = cls.directory / "roottree"
        for subdir in ("usr/bin", "usr/sbin", "usr/lib/systemd/system", "usr/share/www"):
            (cls.rootdir / subdir).mkdir(parents=True, exist_ok=True)
        elf = bytearray(64)
        elf[:6] = b"\x7fELF\x02\x01"
        struct.pack_into("<H", elf, 18, 183)
        for name in ("usr/lib/systemd/systemd", "usr/bin/bmcweb"):
            path = cls.rootdir / name
            path.write_bytes(elf)
            path.chmod(0o755)
        (cls.rootdir / "usr/lib/os-release").write_text(
            'ID=openbmc-phosphor\nNAME="Non-bootable verification test fixture"\n')
        (cls.rootdir / "usr/lib/systemd/system/bmcweb.service").write_text(
            "[Service]\nExecStart=/usr/bin/bmcweb\n")
        (cls.rootdir / "usr/share/www/index.html").write_text(
            "<html><body>Non-bootable verification fixture</body></html>\n")
        (cls.rootdir / "sbin").symlink_to("usr/sbin")
        (cls.rootdir / "usr/sbin/init").symlink_to("../lib/systemd/systemd")
        cls.rootfs = cls.directory / "root.ext4"
        cls.make_rootfs(cls.rootfs)
        dts = cls.directory / "board.dts"
        dts.write_text('/dts-v1/; / { compatible = "xunlong,orangepi-zero2", '
                       '"allwinner,sun50i-h616"; };')
        cls.dtb = cls.directory / "board.dtb"
        VERIFY.command("dtc", "-I", "dts", "-O", "dtb", "-o", cls.dtb, dts)
        cls.fit = cls.make_fit("complete")
        kernel = cls.directory / "Image"
        header = bytearray(64)
        header[56:60] = b"ARM\x64"
        kernel.write_bytes(header)
        cls.bootfs = cls.directory / "boot.fat"
        VERIFY.command("mformat", "-i", cls.bootfs, "-C", "-F", "-T", "131072", "::")
        VERIFY.command("mmd", "-i", cls.bootfs, "::/extlinux")
        config = ROOT / ("meta-orangepi/recipes-bsp/boot/orangepi-boot-files/"
                         "orangepi-zero2-extlinux.conf")
        for source, target in ((kernel, "/Image"),
                               (cls.dtb, "/sun50i-h616-orangepi-zero2.dtb"),
                               (config, "/extlinux/extlinux.conf")):
            VERIFY.command("mcopy", "-i", cls.bootfs, source, "::" + target)
        cls.image = cls.directory / "not-bootable-test-fixture.wic"
        area = boot_fixture()
        area[:512] = mbr_fixture()
        fit = cls.fit.read_bytes()
        area[8192 + 32768:8192 + 32768 + len(fit)] = fit
        with cls.image.open("wb") as output:
            output.write(area)
            with cls.bootfs.open("rb") as source:
                shutil.copyfileobj(source, output)
            output.seek(139264 * 512)
            with cls.rootfs.open("rb") as source:
                shutil.copyfileobj(source, output)
            output.truncate(204800 * 512)

    @classmethod
    def make_rootfs(cls, output):
        with output.open("wb") as image:
            image.truncate(32 * 1024 * 1024)
        VERIFY.command("mkfs.ext4", "-F", "-q", "-L", "root",
                       "-d", cls.rootdir, output)

    @classmethod
    def make_fit(cls, name, bl31=True, load="0x40000000"):
        payload = cls.directory / (name + ".bin")
        payload.write_bytes(b"non-bootable firmware fixture\0" * 128)
        source = cls.directory / (name + ".dts")
        atf_data = f'data = /incbin/("{payload}");' if bl31 else "data = [];"
        source.write_text(f"""/dts-v1/;
/ {{
    images {{
        atf {{
            arch = "arm64"; compression = "none";
            load = <{load}>; entry = <{load}>;
            {atf_data}
        }};
        uboot {{
            arch = "arm64"; compression = "none";
            data = /incbin/("{payload}");
        }};
        fdt-1 {{ type = "flat_dt"; data = /incbin/("{cls.dtb}"); }};
    }};
    configurations {{
        default = "config-1";
        config-1 {{ firmware = "atf"; loadables = "uboot"; fdt = "fdt-1"; }};
    }};
}};
""")
        output = cls.directory / (name + ".fit")
        VERIFY.command("dtc", "-I", "dts", "-O", "dtb", "-o", output, source)
        return output

    def test_complete_structure_and_content_without_modifying_input(self):
        before = self.image.stat().st_mtime_ns
        result = VERIFY.verify(self.image)
        self.assertEqual(result["size"], 204800 * 512)
        self.assertEqual(set(result["firmware"]), {"atf", "uboot"})
        self.assertGreater(result["firmware"]["atf"]["size"], 1024)
        self.assertEqual(result["hardware_boot_test"], "not performed")
        self.assertEqual(self.image.stat().st_mtime_ns, before)

    def test_empty_bl31_is_not_accepted_as_a_bootable_fit(self):
        path = self.make_fit("missing-bl31", bl31=False)
        with self.assertRaisesRegex(VERIFY.InvalidImage, "atf payload"):
            VERIFY.check_fit(path)

    def test_bl31_for_the_wrong_soc_is_rejected(self):
        path = self.make_fit("wrong-address", load="0x104000")
        with self.assertRaisesRegex(VERIFY.InvalidImage, "does not match H616"):
            VERIFY.check_fit(path)

    def test_missing_bmcweb_is_not_hidden_by_debugfs_zero_exit_status(self):
        binary = self.rootdir / "usr/bin/bmcweb"
        backup = self.directory / "saved-bmcweb"
        binary.rename(backup)
        try:
            incomplete = self.directory / "missing-bmcweb.ext4"
            self.make_rootfs(incomplete)
        finally:
            backup.rename(binary)
        with self.assertRaisesRegex(VERIFY.InvalidImage, "bmcweb.*not a"):
            VERIFY.check_rootfs(incomplete)

    def test_compressed_webui_is_supported(self):
        index = self.rootdir / "usr/share/www/index.html"
        backup = self.directory / "saved-index.html"
        compressed = index.with_suffix(".html.gz")
        index.rename(backup)
        try:
            compressed.write_bytes(gzip.compress(backup.read_bytes()))
            image = self.directory / "compressed-webui.ext4"
            self.make_rootfs(image)
        finally:
            compressed.unlink()
            backup.rename(index)
        self.assertIn("openbmc", VERIFY.check_rootfs(image))

    def test_missing_webui_is_rejected(self):
        index = self.rootdir / "usr/share/www/index.html"
        backup = self.directory / "saved-index.html"
        index.rename(backup)
        try:
            image = self.directory / "missing-webui.ext4"
            self.make_rootfs(image)
        finally:
            backup.rename(index)
        with self.assertRaisesRegex(VERIFY.InvalidImage, "Web UI is absent"):
            VERIFY.check_rootfs(image)


if __name__ == "__main__":
    unittest.main()

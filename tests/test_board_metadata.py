"""Fast checks for board metadata contracts with the vendored OE-Core."""
import json
from pathlib import Path
import re
import subprocess
import unittest


ROOT = Path(__file__).resolve().parents[1]
LAYER = ROOT / "meta-orangepi"
CORE = ROOT / "openbmc/upstream-layers/openembedded-core/meta"


class BoardMetadataTest(unittest.TestCase):
    def test_board_recipes_do_not_use_rejected_legacy_git_source_directory(self):
        # do_qa_unpack rejects these even if SRC_URI sets destsuffix=git.
        legacy = re.compile(
            r'^\s*S\s*[?:+]?=\s*[\"\']\$\{(?:WORKDIR|UNPACKDIR)\}/git[\"\']',
            re.MULTILINE,
        )
        for recipe in LAYER.rglob("*.bb"):
            with self.subTest(recipe=str(recipe.relative_to(ROOT))):
                self.assertIsNone(legacy.search(recipe.read_text()))

    def test_tfa_uses_matching_core_source_and_git_checkout_defaults(self):
        recipe = next(LAYER.glob("recipes-bsp/trusted-firmware-a/*.bb")).read_text()
        core = (CORE / "conf/bitbake.conf").read_text()
        self.assertRegex(core, r'(?m)^S = "\$\{UNPACKDIR\}/\$\{BP\}"$')
        self.assertRegex(core, r'(?m)^BB_GIT_DEFAULT_DESTSUFFIX = "\$\{BP\}"$')
        self.assertNotRegex(recipe, r"(?m)^\s*S\s*[?:+]?=")
        self.assertNotIn(";destsuffix=", recipe)
        self.assertIn(";nobranch=1", recipe)

    def test_kernel_and_bootloader_have_cacheable_pinned_sources(self):
        versions = (ROOT / "sources/versions.txt").read_text()
        for name, relative in (
            ("Linux", "recipes-kernel/linux/linux-orangepi_6.1.bb"),
            ("U-Boot", "recipes-bsp/u-boot/u-boot-orangepi.bb"),
        ):
            with self.subTest(recipe=name):
                recipe = (LAYER / relative).read_text()
                revision = re.search(rf"(?m)^{name} commit: ([0-9a-f]+)$", versions)[1]
                self.assertIn(f'SRCREV = "{revision}"', recipe)
                self.assertIn("git://github.com/orangepi-xunlong/", recipe)
                self.assertIn('BB_GIT_SHALLOW = "1"', recipe)
                self.assertNotRegex(recipe, r"(?m)^inherit .*externalsrc")
                if name == "Linux":
                    self.assertGreater(recipe.index('S = "${UNPACKDIR}/${BP}"'),
                                       recipe.index("inherit kernel"))
                for filename in re.findall(r"file://(\S+\.patch)", recipe):
                    patch = (LAYER / relative).parent / "files" / filename
                    self.assertRegex(patch.read_text(), r"(?m)^Upstream-Status: ")

    def test_environment_utilities_are_real_packages_with_safe_file_storage(self):
        recipe = (LAYER / "recipes-bsp/u-boot/u-boot-orangepi.bb").read_text()
        self.assertNotRegex(recipe, r'(?m)^RPROVIDES.*u-boot-fw-utils')
        self.assertIn('RDEPENDS:${PN} += "libubootenv-bin"', recipe)
        provider = (CORE / "recipes-bsp/u-boot/libubootenv_0.3.7.bb").read_text()
        self.assertIn('RPROVIDES:${PN}-bin += "u-boot-fw-utils"', provider)
        config = (LAYER / "recipes-bsp/u-boot/files/fw_env.config").read_text()
        entries = [line.split() for line in config.splitlines()
                   if line.strip() and not line.lstrip().startswith("#")]
        self.assertEqual(entries, [["/boot/uboot.env", "0x0", "0x20000"]])
        machine = (LAYER / "conf/machine/orangepi-zero2.conf").read_text()
        self.assertIn("uboot.env;uboot.env", machine)

    def test_kernel_preflight_exercises_all_patched_vendor_drivers(self):
        recipe_path = LAYER / "recipes-kernel/linux/linux-orangepi_6.1.bb"
        recipe = recipe_path.read_text()
        patches = recipe_path.parent / "files"
        self.assertEqual(set(re.findall(r"file://(\S+\.patch)", recipe)),
                         {path.name for path in patches.glob("*.patch")})
        rtl_patch = (patches / "0003-realtek-fix-separate-build-include-paths.patch").read_text()
        for driver in ("rtl8189es", "rtl8189fs", "rtl8192eu", "rtl8723ds",
                       "rtl8723du", "rtl8811cu", "rtl8812au", "rtl88x2cs"):
            with self.subTest(driver=driver):
                self.assertIn(driver, recipe)
                self.assertIn(f"+++ b/drivers/net/wireless/{driver}/Makefile", rtl_patch)
        self.assertIn("core/rtw_cmd.o", recipe)
        self.assertIn("addtask board_preflight after do_configure", recipe)
        self.assertNotIn("addtask board_preflight after do_configure before", recipe)

    def test_fat_boot_partition_does_not_depend_on_uninstalled_charset_modules(self):
        workflow = (ROOT / ".github/workflows/build-orangepi-zero2-image.yml").read_text()
        recipe = (LAYER / "recipes-kernel/linux/linux-orangepi_6.1.bb").read_text()
        for option in ("VFAT_FS", "NLS_CODEPAGE_437", "NLS_ISO8859_1", "NLS_UTF8"):
            with self.subTest(option=option):
                self.assertIn(f"-e {option}", workflow)
                self.assertIn(option, recipe)

    def test_tf_card_detect_fix_reuses_cached_kernel_dtb(self):
        machine = (LAYER / "conf/machine/orangepi-zero2.conf").read_text()
        recipe = (LAYER / "recipes-bsp/boot/orangepi-fixed-kernel-dtb.bb").read_text()
        patch = (LAYER / "recipes-bsp/u-boot/files/0004-orangepi-zero2-ignore-broken-card-detect.patch").read_text()

        self.assertIn("orangepi-fixed-kernel-dtb", machine)
        self.assertIn(
            "sun50i-h616-orangepi-zero2-openbmc.dtb;sun50i-h616-orangepi-zero2.dtb",
            machine,
        )
        self.assertIn('do_compile[depends] += "virtual/kernel:do_deploy"', recipe)
        self.assertIn("fdtput -d", recipe)
        self.assertIn("broken-cd", recipe)
        self.assertNotIn("file://0004-orangepi-zero2", (LAYER / "recipes-kernel/linux/linux-orangepi_6.1.bb").read_text())
        self.assertIn("arch/arm/dts/sun50i-h616-orangepi-zero2.dts", patch)
        self.assertIn('+\tbroken-cd;', patch)

    def test_wifi_support_reuses_prebuilt_kernel_modules(self):
        packagegroup = (
            LAYER / "recipes-phosphor/packagegroups/packagegroup-orangepi-zero2.bb"
        ).read_text()
        firmware = (
            LAYER / "recipes-bsp/firmware/orangepi-uwe5622-firmware.bb"
        ).read_text()
        support_dir = LAYER / "recipes-connectivity/wifi/orangepi-wifi-support"
        service = (support_dir / "orangepi-wifi.service").read_text()
        network = (support_dir / "80-wlan0.network").read_text()
        modules = (support_dir / "orangepi-uwe5622.conf").read_text().splitlines()

        for package in (
            "kernel-module-uwe5622-bsp-sdio",
            "kernel-module-sprdwl-ng",
            "kernel-module-cfg80211",
            "orangepi-uwe5622-firmware",
            "orangepi-wifi-support",
            "iw",
            "wpa-supplicant",
        ):
            with self.subTest(package=package):
                self.assertIn(package, packagegroup)

        self.assertEqual(modules, ["uwe5622_bsp_sdio", "sprdwl_ng"])
        self.assertIn("modprobe uwe5622_bsp_sdio", service)
        self.assertIn("modprobe sprdwl_ng", service)
        self.assertIn("wpa_supplicant -i wlan0 -D nl80211", service)
        self.assertIn("Name=wlan0", network)
        self.assertIn("DHCP=yes", network)
        self.assertIn("RequiredForOnline=no", network)

        self.assertIn(
            'FIRMWARE_SRCREV = "db5e86200ae592c467c4cfa50ec0c66cbc40b158"',
            firmware,
        )
        self.assertIn("wcnmodem.sha256sum", firmware)
        self.assertIn("boardconfig.sha256sum", firmware)

    def test_ch32v307_kvm_auto_detects_wch_link_and_uses_absolute_coordinates(self):
        bbappend = (
            LAYER / "recipes-graphics/obmc-ikvm/obmc-ikvm_%.bbappend"
        ).read_text()
        files = LAYER / "recipes-graphics/obmc-ikvm/obmc-ikvm"
        service = (files / "obmc-ikvm.service").read_text()
        patch = (files / "0002-add-CH32V307-serial-HID-backend.patch").read_text()
        coordinate_patch = (
            files / "0003-enforce-endpoint-exact-absolute-pointer.patch"
        ).read_text()
        dtb_recipe = (
            LAYER / "recipes-bsp/boot/orangepi-fixed-kernel-dtb.bb"
        ).read_text()
        packagegroup = (
            LAYER / "recipes-phosphor/packagegroups/packagegroup-orangepi-zero2.bb"
        ).read_text()
        firmware = ROOT / "firmware/ch32v307-kvm"

        self.assertIn("0002-add-CH32V307-serial-HID-backend.patch", bbappend)
        self.assertIn("0003-enforce-endpoint-exact-absolute-pointer.patch", bbappend)
        self.assertIn("modprobe cdc_acm", service)
        self.assertIn("--mcu-device auto", service)
        self.assertIn("kernel-module-cdc-acm", packagegroup)
        self.assertIn("mcuKeyboardPacket = 0x01", patch)
        self.assertIn("mcuPointerPacket = 0x02", patch)
        self.assertIn("mcuHeartbeatPacket = 0x03", patch)
        self.assertIn("B921600", patch)
        self.assertIn('wchVendorId = "1a86"', patch)
        self.assertIn('wchLinkProductId = "8010"', patch)
        self.assertIn('wchLinkSysfsTtyPath = "/sys/class/tty"', patch)
        self.assertIn('ttyName.rfind("ttyACM", 0)', patch)
        self.assertIn("hidAbsoluteMaximum = 0x7fff", coordinate_patch)
        self.assertIn("scaleAbsoluteCoordinate(x, video.getWidth())", coordinate_patch)
        self.assertIn("scaleAbsoluteCoordinate(y, video.getHeight())", coordinate_patch)
        self.assertIn("std::clamp<int64_t>", coordinate_patch)
        self.assertIn("MapsBothEndpointsExactly", coordinate_patch)
        self.assertIn("ClampsCoordinatesOutsideTheFramebuffer", coordinate_patch)
        self.assertNotIn("ORANGEPI_UART5_NODE", dtb_recipe)
        self.assertIn('do_compile[depends] += "virtual/kernel:do_deploy"', dtb_recipe)
        self.assertTrue((firmware / "Makefile").is_file())
        self.assertTrue((firmware / "src/kvm_bridge.c").is_file())
        self.assertTrue((firmware / "src/usbd_desc.c").is_file())

    def test_webui_has_complete_default_simplified_chinese_locale(self):
        recipe = (
            LAYER / "recipes-phosphor/webui/webui-vue_%.bbappend"
        ).read_text()
        files = LAYER / "recipes-phosphor/webui/webui-vue"
        additions = json.loads((files / "zh-CN-additions.json").read_text())
        merger = (files / "merge-webui-locales.py").read_text()
        default_language = (files / "default-webui-language.py").read_text()
        kvm_pointer = (
            files / "0001-kvm-use-fixed-absolute-pointer-space.patch"
        ).read_text()

        self.assertIn(
            'CHINESE_LOCALE_SRCREV = "c757b32cc2940f19429af1903d3d0bda9f20c150"',
            recipe,
        )
        self.assertIn(
            'SRC_URI[zhcn.sha256sum] = "3a2e77c4576902b83f6363c9ddf8f78e8cacbe8ca476da5ce1228c8a8949cf21"',
            recipe,
        )
        self.assertIn("merge-webui-locales.py", recipe)
        self.assertIn("Simplified Chinese locale is missing", merger)
        self.assertIn("Simplified Chinese placeholder mismatch", merger)
        self.assertIn("%{", merger)
        self.assertIn("replace_once", default_language)
        self.assertIn("|| 'zh-CN'", default_language)
        self.assertIn("addAlias('zh', 'zh-CN')", default_language)
        self.assertIn("0001-kvm-use-fixed-absolute-pointer-space.patch", recipe)
        self.assertIn("this.rfb.scaleViewport = true", kvm_pointer)
        self.assertIn("this.rfb.clipViewport = false", kvm_pointer)
        self.assertIn("this.rfb.dragViewport = false", kvm_pointer)
        self.assertIn("this.rfb.resizeSession = false", kvm_pointer)
        self.assertEqual(additions["appHeader"]["language"], "语言")
        self.assertEqual(additions["pageNetwork"]["gateway"], "网关")
        self.assertEqual(additions["pageKvm"]["captureScreenshot"], "截取屏幕截图")
        self.assertEqual(
            additions["pageUserManagement"]["toast"]["rootCannotBeSelected"],
            "批量操作不能包含 root 用户。",
        )

    def test_board_recipe_shell_functions_parse(self):
        function = re.compile(r"^do_[\w:]+\(\) \{\n(.*?)^\}", re.MULTILINE | re.DOTALL)
        for recipe in LAYER.rglob("*.bb"):
            for index, body in enumerate(function.findall(recipe.read_text())):
                with self.subTest(recipe=recipe.name, function=index):
                    result = subprocess.run(["bash", "-n"], input=body, text=True,
                                            stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                    self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == "__main__":
    unittest.main()

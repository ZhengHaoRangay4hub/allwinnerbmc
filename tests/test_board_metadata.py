"""Fast checks for board metadata contracts with the vendored OE-Core."""
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

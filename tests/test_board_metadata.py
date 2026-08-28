"""Fast checks for board metadata contracts with the vendored OE-Core."""
from pathlib import Path
import re
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


if __name__ == "__main__":
    unittest.main()

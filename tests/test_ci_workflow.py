"""Guard the separation between board preflight and the image deliverable."""
from pathlib import Path
import re
import unittest


WORKFLOW = (Path(__file__).resolve().parents[1] /
            ".github/workflows/build-orangepi-zero2-image.yml").read_text()


class WorkflowModesTest(unittest.TestCase):
    def test_build_budget_leaves_time_outside_the_compiler(self):
        budget = re.search(
            r"OPENBMC_BUILD_BUDGET_SECONDS: .*&& '([0-9]+)' \|\| '([0-9]+)'",
            WORKFLOW,
        )
        timeout = re.search(
            r"timeout-minutes: .*&& ([0-9]+) \|\| ([0-9]+)", WORKFLOW,
        )
        self.assertIsNotNone(budget)
        self.assertIsNotNone(timeout)
        preflight_seconds, image_seconds = map(int, budget.groups())
        preflight_minutes, image_minutes = map(int, timeout.groups())
        self.assertLessEqual(image_minutes, 360)
        self.assertGreaterEqual(image_minutes * 60 - image_seconds, 30 * 60)
        self.assertGreaterEqual(preflight_minutes * 60 - preflight_seconds, 30 * 60)
        script = (Path(__file__).resolve().parents[1] / "scripts/ci-build-stage.sh").read_text()
        default = int(re.search(r"OPENBMC_BUILD_BUDGET_SECONDS:-([0-9]+)", script)[1])
        self.assertEqual(default, image_seconds)

    def test_hash_equivalence_database_is_in_the_persisted_sstate_directory(self):
        values = {}
        for name in ("SSTATE_DIR", "BB_HASHSERVE_DB_DIR"):
            match = re.search(rf'^\s+{name} = "([^"]+)"$', WORKFLOW, re.MULTILINE)
            self.assertIsNotNone(match, name)
            values[name] = match[1]
        self.assertEqual(values["BB_HASHSERVE_DB_DIR"], values["SSTATE_DIR"])
        self.assertEqual(values["SSTATE_DIR"], "$GITHUB_WORKSPACE/yocto-sstate")

    def test_preflight_preserves_the_existing_image_concurrency_group(self):
        self.assertIn(
            "group: ${{ inputs.preflight_only && 'orangepi-zero2-preflight' || "
            "'orangepi-zero2-openbmc' }}", WORKFLOW)
        self.assertIn("default: false\n        type: boolean", WORKFLOW)

    def test_preflight_does_not_build_an_image_save_cache_or_dispatch_one(self):
        for name in ("Build full OpenBMC image (checkpointable)",
                     "Save Yocto downloads and sstate after build attempt"):
            with self.subTest(step=name):
                step = WORKFLOW.split("      - name: " + name + "\n", 1)[1]
                step = step.split("\n      - name:", 1)[0]
                self.assertIn("!inputs.preflight_only", step)
        continuation = WORKFLOW.split("  continue-checkpointed-build:\n", 1)[1]
        self.assertIn("!inputs.preflight_only", continuation.split("    steps:", 1)[0])
        for name in ("Collect TF-card image and checksums", "Upload TF-card image"):
            with self.subTest(step=name):
                step = WORKFLOW.split("      - name: " + name + "\n", 1)[1]
                step = step.split("\n      - name:", 1)[0]
                self.assertIn("steps.build_image.outcome == 'success'", step)

    def test_preflight_compiles_real_kernel_objects_and_rejects_timeout(self):
        self.assertIn("bitbake -c board_preflight virtual/kernel", WORKFLOW)
        self.assertIn("patch --batch --forward --fuzz=0", WORKFLOW)
        guard = WORKFLOW.split("      - name: Require completed boot preflight\n", 1)[1]
        guard = guard.split("\n      - name:", 1)[0]
        self.assertIn("steps.build_boot.outputs.checkpointed == 'true'", guard)
        self.assertIn("exit 1", guard)


if __name__ == "__main__":
    unittest.main()

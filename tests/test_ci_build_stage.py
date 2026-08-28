"""Exercise CI exit/timeout handling without starting a real Yocto build."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest


SCRIPT = Path(__file__).resolve().parents[1] / "scripts/ci-build-stage.sh"


class BuildStageTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="orangepi-ci-test-")
        self.addCleanup(self.temp.cleanup)
        self.workspace = Path(self.temp.name)
        self.bin = self.workspace / "bin"
        self.bin.mkdir()
        self.deploy = self.workspace / "yocto-tmp/deploy/images/orangepi-zero2"
        self.deploy.mkdir(parents=True)
        self.output = self.workspace / "github-output"
        self.env_file = self.workspace / "github-env"
        self.calls = self.workspace / "calls.json"
        self.env = dict(os.environ)
        self.env.pop("OPENBMC_BUILD_DEADLINE", None)
        self.env.update(
            PATH=f"{self.bin}:{os.environ['PATH']}",
            GITHUB_WORKSPACE=str(self.workspace),
            GITHUB_OUTPUT=str(self.output),
            GITHUB_ENV=str(self.env_file),
            OPENBMC_BUILD_BUDGET_SECONDS="18000",
            TEST_CALLS=str(self.calls),
        )
        self.write_tool("timeout", """
import os, subprocess, sys
if 'TEST_TIMEOUT_RC' in os.environ:
    print(os.environ.get('TEST_LOG', 'simulated timeout'))
    sys.exit(int(os.environ['TEST_TIMEOUT_RC']))
sys.exit(subprocess.call(sys.argv[4:]))
""")
        self.write_tool("bitbake", """
import json, os, pathlib, sys
pathlib.Path(os.environ['TEST_CALLS']).write_text(json.dumps(sys.argv[1:]))
print(os.environ.get('TEST_LOG', 'simulated BitBake'))
rc = int(os.environ.get('TEST_BUILD_RC', '0'))
if rc == 0 and os.environ.get('TEST_OUTPUTS', '1') == '1':
    deploy = pathlib.Path(os.environ['GITHUB_WORKSPACE']) / 'yocto-tmp/deploy/images/orangepi-zero2'
    names = ['u-boot-sunxi-with-spl.bin', 'uboot.env', 'orangepi-zero2-extlinux.conf'] if 'u-boot-orangepi' in sys.argv else ['test.wic']
    for name in names:
        (deploy / name).write_bytes(b'test fixture only')
sys.exit(rc)
""")

    def write_tool(self, name, body):
        tool = self.bin / name
        tool.write_text(f"#!{sys.executable}\n{body}")
        tool.chmod(0o755)

    def run_stage(self, stage="image", **env):
        return subprocess.run(
            ["bash", str(SCRIPT), stage], env={**self.env, **env},
            text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            timeout=15,
        )

    def checkpoint(self):
        return self.output.read_text().strip()

    def test_boot_stage_builds_image_dependencies_first(self):
        result = self.run_stage("boot")
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertEqual(json.loads(self.calls.read_text()),
                         ["u-boot-orangepi", "orangepi-boot-files"])
        self.assertEqual(self.checkpoint(), "checkpointed=false")
        self.assertIn("OPENBMC_BUILD_DEADLINE=", self.env_file.read_text())

    def test_image_uses_keep_going_and_existing_deadline(self):
        result = self.run_stage(OPENBMC_BUILD_DEADLINE=str(int(time.time()) + 120))
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertEqual(json.loads(self.calls.read_text()), ["-k", "obmc-phosphor-image"])
        self.assertFalse(self.env_file.exists(), "the second stage must not reset the budget")
        self.assertEqual(self.checkpoint(), "checkpointed=false")

    def test_recipe_failure_is_not_hidden_by_a_stale_image(self):
        (self.deploy / "old.wic").write_bytes(b"old test fixture")
        result = self.run_stage(TEST_BUILD_RC="1", TEST_LOG="ERROR: recipe failed")
        self.assertEqual(result.returncode, 1)
        self.assertEqual(self.checkpoint(), "checkpointed=false")

    def test_success_without_image_is_failure(self):
        result = self.run_stage(TEST_OUTPUTS="0")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("without a TF-card image", result.stdout)

    def test_boot_success_requires_all_deployed_files(self):
        (self.deploy / "u-boot-sunxi-with-spl.bin").write_bytes(b"test fixture")
        result = self.run_stage("boot", TEST_OUTPUTS="0")
        self.assertNotEqual(result.returncode, 0)

    def test_controlled_timeout_is_a_checkpoint(self):
        result = self.run_stage(TEST_TIMEOUT_RC="124")
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertEqual(self.checkpoint(), "checkpointed=true")

    def test_timeout_after_recipe_error_requires_repair(self):
        result = self.run_stage(TEST_TIMEOUT_RC="124", TEST_LOG="ERROR: recipe failed")
        self.assertEqual(result.returncode, 1)
        self.assertEqual(self.checkpoint(), "checkpointed=false")

    def test_early_sigkill_is_not_a_timeout(self):
        result = self.run_stage(TEST_TIMEOUT_RC="137")
        self.assertEqual(result.returncode, 137)
        self.assertEqual(self.checkpoint(), "checkpointed=false")

    def test_early_sigterm_is_not_a_timeout(self):
        result = self.run_stage(TEST_TIMEOUT_RC="143")
        self.assertEqual(result.returncode, 143)
        self.assertEqual(self.checkpoint(), "checkpointed=false")

    def test_expired_shared_budget_does_not_start_another_build(self):
        result = self.run_stage(OPENBMC_BUILD_DEADLINE="1")
        self.assertEqual(result.returncode, 0)
        self.assertEqual(self.checkpoint(), "checkpointed=true")
        self.assertFalse(self.calls.exists())

    def test_log_write_failure_cannot_report_success(self):
        self.write_tool("tee", "import sys\nsys.stdin.read()\nsys.exit(1)\n")
        result = self.run_stage()
        self.assertEqual(result.returncode, 1)
        self.assertEqual(self.checkpoint(), "checkpointed=false")


if __name__ == "__main__":
    unittest.main()

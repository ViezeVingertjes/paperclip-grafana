import os
import stat
import subprocess
import sys
import tempfile
import unittest

from tests.helpers import ROOT

SCRIPT = os.path.join(ROOT, "paperclip-otel", "apply-paperclip-otel.py")


class ApplyOtel(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = os.path.join(self.tmp.name, "paperclip.env")

    def tearDown(self):
        self.tmp.cleanup()

    def run_script(self, *args, name=None):
        env = {k: v for k, v in os.environ.items() if k != "PAPERCLIP_SERVICE_NAME"}
        if name:
            env["PAPERCLIP_SERVICE_NAME"] = name
        subprocess.run([sys.executable, "-I", SCRIPT, self.path, *args], env=env, check=True, capture_output=True)
        with open(self.path) as f:
            return f.read().splitlines()

    def write(self, text):
        with open(self.path, "w") as f:
            f.write(text)

    def test_adds_the_trace_variables(self):
        lines = self.run_script()
        self.assertIn("OTEL_EXPORTER_OTLP_ENDPOINT=http://otel-lgtm:4317", lines)
        self.assertIn("OTEL_EXPORTER_OTLP_PROTOCOL=grpc", lines)
        self.assertIn("OTEL_SERVICE_NAME=paperclip", lines)

    def test_service_name_comes_from_the_environment_or_the_flag(self):
        self.assertIn("OTEL_SERVICE_NAME=staging", self.run_script(name="staging"))
        self.assertIn("OTEL_SERVICE_NAME=other", self.run_script("--service-name", "other", name="staging"))

    def test_endpoint_and_protocol_can_be_changed(self):
        lines = self.run_script("--endpoint", "http://127.0.0.1:4318", "--protocol", "http/protobuf")
        self.assertIn("OTEL_EXPORTER_OTLP_ENDPOINT=http://127.0.0.1:4318", lines)
        self.assertIn("OTEL_EXPORTER_OTLP_PROTOCOL=http/protobuf", lines)

    def test_keeps_other_lines_and_makes_a_backup(self):
        self.write("# secrets\nBETTER_AUTH_SECRET=abc\nOTEL_SERVICE_NAME=old\n")
        lines = self.run_script()
        self.assertEqual(lines[:2], ["# secrets", "BETTER_AUTH_SECRET=abc"])
        self.assertEqual([line for line in lines if line.startswith("OTEL_SERVICE_NAME")], ["OTEL_SERVICE_NAME=paperclip"])
        self.assertTrue(os.path.exists(self.path + ".bak-pre-otel"))

    def test_native_flag_adds_the_provider_pack_variables(self):
        lines = self.run_script("--native")
        self.assertIn("PAPERCLIP_ACPX_PROVIDER_PACKAGE_ROOT=/opt/paperclip-runner/provider-pack", lines)
        self.assertIn("PAPERCLIP_ACPX_PROVIDER_PACKAGE_MANIFEST=/opt/paperclip-runner/provider-pack/package.json", lines)
        self.assertIn("OTEL_SERVICE_NAME=paperclip", lines)

    def test_native_variables_are_left_out_unless_asked_for(self):
        self.assertFalse([line for line in self.run_script() if line.startswith("PAPERCLIP_ACPX_")])

    def test_remove_also_takes_the_native_variables_out(self):
        self.write("KEEP=1\n")
        self.run_script("--native")
        lines = self.run_script("--remove")
        self.assertEqual(lines, ["KEEP=1"])

    def test_backup_keeps_the_permissions_of_a_secrets_file(self):
        self.write("BETTER_AUTH_SECRET=abc\n")
        os.chmod(self.path, 0o600)
        self.run_script()
        self.assertEqual(stat.S_IMODE(os.stat(self.path + ".bak-pre-otel").st_mode), 0o600)

    def test_is_idempotent(self):
        first = self.run_script()
        self.assertEqual(self.run_script(), first)

    def test_remove_takes_everything_out_again(self):
        self.write("FOO=bar\n")
        self.run_script()
        self.assertEqual(self.run_script("--remove"), ["FOO=bar"])

    def test_a_commented_variable_is_left_alone(self):
        self.write("# OTEL_SERVICE_NAME=documented\n")
        self.assertIn("# OTEL_SERVICE_NAME=documented", self.run_script())


if __name__ == "__main__":
    unittest.main()

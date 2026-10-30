import json
import os
import subprocess
import sys
import tempfile
import unittest

from tests.helpers import ROOT

SCRIPT = os.path.join(ROOT, "paperclip-otel", "peer-packages.py")
PEERS = {
    "@opentelemetry/sdk-node": "0.300.0",
    "@opentelemetry/auto-instrumentations-node": "0.90.0",
    "@opentelemetry/resources": "3.0.0",
    "@opentelemetry/semantic-conventions": "1.50.0",
    "@opentelemetry/exporter-trace-otlp-grpc": "0.300.1",
    "@opentelemetry/exporter-trace-otlp-http": "0.300.2",
    "@opentelemetry/exporter-trace-otlp-proto": "0.300.3",
    "@sentry/node": "10.0.0",
}


class PeerPackages(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        os.makedirs(os.path.join(self.tmp.name, "server"))
        self.manifest = os.path.join(self.tmp.name, "server", "package.json")
        self.write(PEERS)

    def tearDown(self):
        self.tmp.cleanup()

    def write(self, peers):
        with open(self.manifest, "w") as f:
            json.dump({"name": "@paperclipai/server", "peerDependencies": peers}, f)

    def run_script(self, *args, path=None):
        return subprocess.run([sys.executable, "-I", SCRIPT, path or self.tmp.name, *args], capture_output=True, text=True)

    def test_reads_the_exact_versions_the_paperclip_declares(self):
        out = json.loads(self.run_script("--json").stdout)
        self.assertEqual(out["@opentelemetry/sdk-node"], "0.300.0")
        self.assertEqual(out["@opentelemetry/exporter-trace-otlp-grpc"], "0.300.1")

    def test_exactly_one_exporter_for_the_chosen_protocol(self):
        for protocol, exporter in (("grpc", "grpc"), ("http/protobuf", "proto"), ("http/json", "http")):
            out = json.loads(self.run_script("--json", "--protocol", protocol).stdout)
            exporters = [n for n in out if "exporter-trace-otlp" in n]
            self.assertEqual(exporters, [f"@opentelemetry/exporter-trace-otlp-{exporter}"])

    def test_accepts_a_checkout_the_server_directory_or_the_manifest(self):
        for path in (self.tmp.name, os.path.join(self.tmp.name, "server"), self.manifest):
            self.assertEqual(self.run_script("--json", path=path).returncode, 0, path)

    def test_prints_a_pnpm_command_and_the_variables(self):
        out = self.run_script().stdout
        self.assertIn("pnpm add @opentelemetry/sdk-node@0.300.0", out)
        self.assertIn("OTEL_EXPORTER_OTLP_PROTOCOL=grpc", out)

    def test_a_paperclip_without_opentelemetry_peers_fails_clearly(self):
        self.write({"@sentry/node": "10.0.0"})
        result = self.run_script()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("does not declare", result.stderr)

    def test_the_real_packages_in_the_containerfile_follow_the_manifest_not_a_pin(self):
        with open(os.path.join(ROOT, "paperclip-otel", "Containerfile"), encoding="utf-8") as f:
            text = f.read()
        self.assertIn("peerDependencies", text)
        self.assertNotRegex(text, r"@opentelemetry/[a-z-]+@\d")   # no hard-coded version


if __name__ == "__main__":
    unittest.main()

import contextlib
import io
import json
import os
import re
import unittest

from tests.helpers import ROOT, load

sample = load("send_sample_telemetry", "tools/send_sample_telemetry.py")


def dashboard_queries():
    with open(os.path.join(ROOT, "dashboards", "paperclip.json"), encoding="utf-8") as f:
        d = json.load(f)
    return [t.get("expr") or t.get("query", "") for p in d["panels"] for t in p.get("targets", [])]


def sent_spans(payload):
    return [s for rs in payload["resourceSpans"] for ss in rs["scopeSpans"] for s in ss["spans"]]


def attr_keys(span):
    return {a["key"] for a in span["attributes"]}


class SampleTelemetryCoversTheDashboard(unittest.TestCase):
    def setUp(self):
        self.sent = {}
        self.addCleanup(setattr, sample, "post", sample.post)
        sample.post = lambda path, body: self.sent.setdefault(path, body)
        with contextlib.redirect_stdout(io.StringIO()):
            sample.main()
        self.spans = sent_spans(self.sent["/v1/traces"])
        self.queries = " ".join(dashboard_queries())

    def test_sends_traces_only(self):
        # Paperclip exports traces and nothing else.
        self.assertEqual(list(self.sent), ["/v1/traces"])

    def test_covers_every_exact_span_name_the_dashboard_queries(self):
        used = set(re.findall(r'(?<![.\w])name\s*=\s*"([^"]+)"', self.queries)) | set(re.findall(r'span_name="([^"]+)"', self.queries))
        self.assertTrue(used, 'no name = "..." found in the dashboard, check the regex')
        self.assertEqual(used - {s["name"] for s in self.spans}, set())

    def test_every_span_name_pattern_matches_a_sample_span(self):
        names = {s["name"] for s in self.spans}
        patterns = set(re.findall(r'(?<![.\w])name\s*=~\s*"([^"]+)"', self.queries)) | set(re.findall(r'span_name=~"([^"]+)"', self.queries))
        self.assertTrue(patterns, 'no name =~ "..." found in the dashboard, check the regex')
        for pat in patterns:
            rx = re.compile(pat.replace("\\\\", "\\"))   # the query string holds the regex with doubled backslashes
            self.assertTrue(any(rx.fullmatch(n) for n in names), pat)

    def test_covers_every_span_attribute_the_dashboard_reads(self):
        used = set(re.findall(r"span\.([A-Za-z0-9_.]+?)(?=[\s,)=!>]|$)", self.queries))
        used |= {m.replace("span.", "", 1) for m in re.findall(r"\b(span\.paperclip\.[A-Za-z0-9_.]+)", self.queries)}
        used = {u for u in used if u.startswith(("paperclip.", "budget.", "http.", "url."))}
        self.assertTrue(used, "no span attribute found in the dashboard, check the regex")
        sent = set().union(*(attr_keys(s) for s in self.spans))
        self.assertEqual(used - sent, set())

    def test_has_failed_runs_and_failed_tools(self):
        failed = {s["name"] for s in self.spans if s["status"]["code"] == sample.ERROR}
        self.assertIn("task.provider_session", failed)
        self.assertIn("task.execution_attempt", failed)
        self.assertIn("tool.execute", failed)
        self.assertIn("controller.startup.native_recovery", failed)

    def test_has_server_spans_with_stable_http_attributes(self):
        server = [s for s in self.spans if s["kind"] == sample.SERVER]
        self.assertTrue(server)
        for span in server:
            self.assertTrue({"http.request.method", "http.response.status_code", "url.path"} <= attr_keys(span))

    def test_run_ids_are_hashes_not_uuids(self):
        ids = {a["value"]["stringValue"] for s in self.spans for a in s["attributes"] if a["key"] == "paperclip.task.run.run_id"}
        self.assertTrue(all(re.fullmatch(r"[0-9a-f]{12}", i) for i in ids))

    def test_payloads_are_json_serialisable(self):
        for body in self.sent.values():
            json.dumps(body)


if __name__ == "__main__":
    unittest.main()

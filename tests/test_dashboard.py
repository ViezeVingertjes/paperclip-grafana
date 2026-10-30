import json
import os
import subprocess
import sys
import unittest

from tests.helpers import ROOT, load

gen = load("gen_dashboard", "tools/gen_dashboard.py")


def targets(dashboard):
    return [(p["title"], t) for p in dashboard["panels"] for t in p.get("targets", [])]


def query(t):
    return t.get("expr") or t.get("query", "")


class GeneratedDashboard(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.d = gen.dashboard

    def test_has_instance_variable_and_datasource_variables(self):
        names = [v["name"] for v in self.d["templating"]["list"]]
        self.assertEqual(names, ["service", "ds_prometheus", "ds_tempo"])

    def test_panel_ids_are_unique(self):
        ids = [p["id"] for p in self.d["panels"]]
        self.assertEqual(len(ids), len(set(ids)))

    def test_only_prometheus_and_tempo_are_queried(self):
        # Paperclip exports traces only: there is no Loki signal to query.
        for title, t in targets(self.d):
            self.assertIn(t["datasource"]["type"], ("prometheus", "tempo"), title)

    def test_every_query_is_scoped_to_the_selected_instance(self):
        for title, t in targets(self.d):
            q = query(t)
            if t["datasource"]["type"] == "prometheus":
                self.assertIn('service=~"$service"', q, title)
            else:
                self.assertIn("${service:regex}", q, title)

    def test_every_span_metric_is_a_traces_spanmetrics_series(self):
        for title, t in targets(self.d):
            if t["datasource"]["type"] == "prometheus":
                self.assertIn("traces_spanmetrics_", query(t), title)

    def test_latency_percentiles_never_come_from_span_metric_buckets(self):
        # Span-metric histograms stop at 16.4 s and agent runs last minutes, so a histogram_quantile would saturate.
        for title, t in targets(self.d):
            self.assertNotIn("histogram_quantile", query(t), title)
            self.assertNotIn("traces_spanmetrics_latency_bucket", query(t), title)

    def test_queries_are_balanced(self):
        for title, t in targets(self.d):
            q = query(t)
            for open_, close in ("()", "{}", "[]"):
                self.assertEqual(q.count(open_), q.count(close), f"{title}: {q}")

    def test_metrics_queries_are_instant_or_range(self):
        for title, t in targets(self.d):
            if "metricsQueryType" in t:
                self.assertIn(t["metricsQueryType"], ("range", "instant"), title)
                self.assertEqual(t["datasource"]["type"], "tempo", title)

    def test_committed_dashboard_matches_the_generator(self):
        out = subprocess.run([sys.executable, "-I", os.path.join(ROOT, "tools", "gen_dashboard.py")],
                             check=True, capture_output=True, text=True).stdout
        with open(os.path.join(ROOT, "dashboards", "paperclip.json"), encoding="utf-8") as f:
            committed = f.read()
        self.assertEqual(json.loads(out), json.loads(committed),
                         "dashboards/paperclip.json is stale: run  python3 tools/gen_dashboard.py > dashboards/paperclip.json")


if __name__ == "__main__":
    unittest.main()

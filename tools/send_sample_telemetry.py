#!/usr/bin/env python3
"""Push sample OTLP traces to an otel-lgtm stack (OTLP/HTTP JSON), so tools/validate_dashboard.py has something to
query instead of an empty Grafana.

Paperclip exports traces only, so this sends traces only: Tempo derives the span metrics from them. Covers every span
name and span attribute the dashboard queries (see docs/telemetry-reference.md): native agent runs with their full
lifecycle (one failed), execution preparation and workspace sync, controller phases (one failed), budget, Slack
receipts, and the HTTP and PostgreSQL auto-instrumentation spans.

  tools/send_sample_telemetry.py [otlp-http-base-url]   (default http://127.0.0.1:4318, or $OTLP_URL)
"""
import hashlib, json, os, random, sys, time, urllib.request

OTLP = (sys.argv[1] if len(sys.argv) > 1 and sys.argv[1].startswith("http") else os.environ.get("OTLP_URL", "http://127.0.0.1:4318")).rstrip("/")
NOW = time.time()
# Not "paperclip": if this ever reaches a stack that holds real telemetry, it shows up as its own instance, never as yours.
SERVICE = os.environ.get("SAMPLE_SERVICE_NAME", "paperclip-sample")
NS = "paperclip.native.span."
RNG = random.Random(7)   # fixed seed: the same sample every run

INTERNAL, SERVER, CLIENT = 1, 2, 3
OK, ERROR = 1, 2

PROVIDERS = ["claude", "codex", "opencode"]
TOOLS = ["issue.create", "issue.comment", "approval.request", "other"]


def ns(t):
    return str(int(t * 1e9))


def attrs(**kv):
    out = []
    for k, v in kv.items():
        k = k.replace("__", ".")   # python identifiers cannot hold dots
        val = {"boolValue": v} if isinstance(v, bool) else {"doubleValue": v} if isinstance(v, float) else (
            {"intValue": v} if isinstance(v, int) else {"stringValue": str(v)})
        out.append({"key": k, "value": val})
    return out


def post(path, body):
    req = urllib.request.Request(OTLP + path, data=json.dumps(body).encode(), headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=10) as r:
        r.read()


def rand_id(nbytes):
    """traceId/spanId take hex in OTLP/JSON (the collector's ID type has its own JSON mapping, unlike other bytes fields)."""
    return os.urandom(nbytes).hex()


class Trace:
    """Collects the spans of one trace; add() returns the new span's id so children can point at it."""

    def __init__(self):
        self.id = rand_id(16)
        self.spans = []

    def add(self, parent, name, t0, t1, kind=INTERNAL, failed=False, **fields):
        sid = rand_id(8)
        s = {"traceId": self.id, "spanId": sid, "name": name, "kind": kind, "startTimeUnixNano": ns(t0), "endTimeUnixNano": ns(t1),
             "attributes": attrs(**fields), "status": {"code": ERROR if failed else OK}}
        if parent:
            s["parentSpanId"] = parent
        self.spans.append(s)
        return sid


def run_hash(i):
    return hashlib.sha256(f"sample-run-{i}".encode()).hexdigest()[:12]


def native_run(i, t0, provider, failed=False, resumed=False):
    """One native run: the trace schema v3 lifecycle from doc/observability.md, scaled to a few minutes."""
    tr = Trace()
    rid = run_hash(i)
    q, prep, startup, turn, settle = 4 + i % 3, 18 + i % 5, 14 + i % 4, 60 + 12 * (i % 4), 6
    t = t0
    root_end = t0 + q + prep + startup + turn + settle
    root = tr.add("", "task.provider_session", t0, root_end, failed=failed,
                  **{"paperclip.task.run.run_id": rid, "paperclip.task.run.runtime": "paperclip_runner", "paperclip.task.run.trace_schema_version": 3,
                     "paperclip.task.run.wall_ms": int((root_end - t0) * 1000), "paperclip.task.run.outcome": "failed" if failed else "ok"})
    tr.add(root, "heartbeat.queue", t, t + q, **{NS + "outcome": "ok"})
    t += q
    p = tr.add(root, "task.prepare", t, t + prep)
    env = tr.add(p, "environment.startup", t, t + prep * 0.6)
    tr.add(env, "environment.acquire", t, t + prep * 0.25)
    tr.add(env, "environment.workspace.realize", t + prep * 0.25, t + prep * 0.6)
    tr.add(p, "skills.prepare", t + prep * 0.6, t + prep * 0.7)
    tr.add(p, "heartbeat.prepare_before_environment", t, t + prep * 0.2)
    tr.add(p, "heartbeat.prepare_after_environment", t + prep * 0.6, t + prep * 0.9)
    tr.add(p, "native.coordinator.claim", t + prep * 0.9, t + prep)
    t += prep
    ex = tr.add(root, "native.session.execute", t, t + startup + turn, failed=failed, **{
        NS + "provider": provider, NS + "harness": "acpx" if provider != "opencode" else "opencode", NS + "lifecycleMode": "warm" if resumed else "fresh",
        NS + "bytesTransferred": 40_000_000 + i * 3_000_000, NS + "outcome": "failed" if failed else "ok", NS + "trace_schema_version": 3})
    st = tr.add(ex, "runner.session.startup", t, t + startup)
    c = tr.add(st, "runner.transport.connect", t, t + startup * 0.3)
    tr.add(c, "runner.artifact.prepare", t, t + startup * 0.2)
    tr.add(st, "runner.transport.activation", t + startup * 0.3, t + startup * 0.4)
    tr.add(st, "runner.transport.ready", t + startup * 0.4, t + startup * 0.5)
    rs = tr.add(st, "runner.runtime.stage", t + startup * 0.5, t + startup * 0.8)
    sy = tr.add(rs, "stage.sync", t + startup * 0.5, t + startup * 0.8)
    h = tr.add(sy, "stage.asset.home", t + startup * 0.5, t + startup * 0.65)
    tr.add(h, "session.checkpoint.restore", t + startup * 0.5, t + startup * 0.6)
    tr.add(sy, "stage.asset.runtime_context", t + startup * 0.6, t + startup * 0.7)
    tr.add(sy, "stage.asset.ca_bundle", t + startup * 0.7, t + startup * 0.75)
    tr.add(st, "runner.session.resume" if resumed else "runner.session.bootstrap", t + startup * 0.8, t + startup * 0.95)
    tr.add(st, "runner.turn.submit", t + startup * 0.95, t + startup)
    t += startup
    at = tr.add(ex, "agent.turn", t, t + turn, failed=failed, **{NS + "provider": provider})
    tr.add(at, "runner.turn.submitted_to_started", t, t + 1.5 + i % 3)
    tr.add(at, "provider.time_to_first_agent_event", t, t + 5 + i % 4)
    for k in range(3 + i % 3):
        op = TOOLS[(i + k) % len(TOOLS)]
        ts0 = t + 10 + k * 9
        bad = failed and k == 0
        tr.add(at, "tool.request.input_stream", ts0 - 2, ts0, **{NS + "operation": op})
        tr.add(at, "tool.execute", ts0, ts0 + (7.5 if k == 2 else 0.6 + 0.2 * k), failed=bad, **{NS + "operation": op})
    tr.add(root, "task.time_to_first_token", t0, t + 9 + i % 4, **{NS + "eventKind": "agentMessage" if i % 2 else "reasoning", NS + "duration_ms": 9000})
    t += turn
    se = tr.add(root, "task.settle", t, t + settle)
    tr.add(se, "native.result.finalize", t, t + settle * 0.6)
    tr.add(se, "session.checkpoint.persist", t + settle * 0.6, t + settle)
    return tr


def execution_attempt(i, t0):
    """Server-side attempt: preparation phases and the detailed workspace spans (paperclip.execution tracer)."""
    tr = Trace()
    rid = {"paperclip.task.run.run_id": run_hash(i)}
    end = t0 + 30
    root = tr.add("", "task.execution_attempt", t0, end, **rid)
    ws = tr.add(root, "heartbeat.prepare.workspace", t0, t0 + 20, **rid)
    tr.add(ws, "heartbeat.prepare.workspace_source_materialize", t0 + 1, t0 + 12, **rid)
    tr.add(ws, "heartbeat.prepare.workspace_provisioning", t0 + 12, t0 + 15, **rid)
    tr.add(ws, "heartbeat.prepare.workspace_repository_admission", t0 + 15, t0 + 19, **rid)
    outcome = ["hit", "miss", "published", "disabled"][i % 4]
    tr.add(ws, "workspace.checkout.git_clone", t0 + 2, t0 + 9, **{"paperclip.execution.repositoryCache.outcome": outcome,
                                                                   "paperclip.execution.repositoryCache.reference_supplied": outcome == "hit"})
    tr.add(ws, "workspace.checkout.cache_lookup", t0 + 1, t0 + 2, **{"paperclip.execution.repositoryCache.outcome": outcome})
    sync = tr.add(root, "runtime_selection.workspace_sync", t0 + 20, t0 + 29)
    for j, name in enumerate(["workspace_sync.stage_workspace", "workspace_sync.transfer", "workspace_sync.pack", "workspace_sync.snapshot_git",
                              "workspace_sync.snapshot_baseline", "workspace_sync.seed_lookup", "workspace_sync.inbound_barrier", "workspace_sync.git_clone"]):
        tr.add(sync, name, t0 + 20 + j * 0.5, t0 + 21 + j * 0.9, **({"paperclip.execution.fileCount": 120 + i, "paperclip.execution.bytes": 5_000_000 + 400_000 * j}
                                                                       if name.endswith(("transfer", "pack")) else {}))
    return tr


def controller_phases(t0):
    tr = Trace()
    for j, name in enumerate(["controller.startup.tool_reviews", "controller.startup.gateway_sessions", "controller.startup.accounting",
                              "controller.startup.plugin_workers", "controller.startup.native_recovery", "controller.startup.queued_runs"]):
        tr.add("", name, t0 + j, t0 + j + 0.4 + 0.5 * j, failed=name.endswith("native_recovery"))
    return tr


def reconciliation(t0):
    tr = Trace()
    root = tr.add("", "controller.native_reconciliation", t0, t0 + 3.2, **{"paperclip.native_reconciliation.scoped": True, "paperclip.native_reconciliation.candidates": 4})
    for j, name in enumerate(["legacy_workspace_exports", "obsolete_policy_reviews", "automatic_completion_reviews", "candidate_scan", "candidates"]):
        tr.add(root, name, t0 + j * 0.5, t0 + j * 0.5 + 0.5)
    return tr


def budget(t0):
    tr = Trace()
    for j, name in enumerate(["budget.admission.evaluate", "budget.admission.reserve", "budget.accounting.transaction", "budget.accounting.settlement",
                              "budget.accounting.lock_wait", "budget.exposure.evaluate", "budget.enforcement.deliver", "budget.enforcement.scope",
                              "budget.cancellation.deliver", "budget.accounting.recover"]):
        extra = {"budget.policy_count": 2} if name.startswith("budget.admission") else {}
        if name == "budget.enforcement.deliver":
            extra["budget.enforcement.queue_delay_ms"] = 800 + 200 * (int(t0) % 5)
        tr.add("", name, t0 + j * 0.2, t0 + j * 0.2 + 0.05 + 0.03 * j, **extra)
    return tr


def issue_read(t0):
    tr = Trace()
    for j, name in enumerate(["lookup", "authorization", "ancestors", "documents", "blockers", "relations", "workspace", "execution_blocker"]):
        tr.add("", f"issue.read.{name}", t0 + j * 0.05, t0 + j * 0.05 + 0.02 * (j + 1))
    return tr


def slack(t0):
    tr = Trace()
    for j, (op, out) in enumerate([("add", "confirmed"), ("add", "confirmed"), ("add", "failed"), ("remove", "confirmed")]):
        tr.add("", "chat.slack.receipt", t0 + j, t0 + j + 0.3, failed=out == "failed", **{
            "paperclip.chat.receipt.operation": op, "paperclip.chat.receipt.outcome": out,
            "paperclip.chat.receipt.queue_ms": 120 + 30 * j, "paperclip.chat.receipt.delivery_age_ms": 900 + 250 * j})
    return tr


def http_request(t0, route, db_op, slow=False, failed=False):
    """A server span with a PostgreSQL client child, as the HTTP and pg auto-instrumentation produce them."""
    tr = Trace()
    dur = 0.12 + (0.9 if slow else 0)
    root = tr.add("", f"GET {route}", t0, t0 + dur, kind=SERVER, failed=failed, **{"http.route": route, "http.method": "GET", "http.status_code": 500 if failed else 200})
    tr.add(root, f"pg.query:{db_op}", t0 + 0.01, t0 + 0.01 + (0.8 if slow else 0.03), kind=CLIENT, **{
        "db.system": "postgresql", "db.operation": db_op, "db.statement": f"{db_op} id, status FROM issues WHERE company_id = $1"})
    return tr


def all_traces():
    out = []
    for i in range(6):
        out.append(native_run(i, NOW - 1500 + i * 200, PROVIDERS[i % 3], failed=(i == 4), resumed=(i % 3 == 2)))
        out.append(execution_attempt(i, NOW - 1500 + i * 200 - 40))
    for k in range(4):
        out.append(controller_phases(NOW - 900 + k * 120))
        out.append(reconciliation(NOW - 800 + k * 120))
        out.append(budget(NOW - 700 + k * 90))
        out.append(issue_read(NOW - 600 + k * 60))
        out.append(slack(NOW - 500 + k * 60))
    for k in range(12):
        out.append(http_request(NOW - 400 + k * 20, "/api/issues/:id", "SELECT", slow=(k == 3)))
        out.append(http_request(NOW - 390 + k * 20, "/api/companies/:companyId/agents", "SELECT", failed=(k == 7)))
        out.append(http_request(NOW - 380 + k * 20, "/api/runs", "INSERT"))
    return out


def send_traces():
    spans = [s for tr in all_traces() for s in tr.spans]
    resource = {"attributes": attrs(**{"service.name": SERVICE, "service.version": "ci-sample"})}
    post("/v1/traces", {"resourceSpans": [{"resource": resource, "scopeSpans": [{"scope": {"name": "sample-telemetry"}, "spans": spans}]}]})
    return len(spans)


def main():
    count = send_traces()
    print(f"sample telemetry sent to {OTLP}: {count} spans, service.name={SERVICE}")


if __name__ == "__main__":
    main()

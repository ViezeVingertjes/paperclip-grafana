# Telemetry reference

What Paperclip exports, and what the dashboard does with it. Names were taken from the Paperclip source and its
[`doc/observability.md`](https://github.com/paperclipai/paperclip/blob/master/doc/observability.md) at commit `b31ec0a`
and can change between versions; if a panel goes empty after an upgrade, compare this list with the spans in your Tempo.

## What Paperclip exports

**Traces only.** The server has opt-in OpenTelemetry auto-instrumentation: with `OTEL_EXPORTER_OTLP_ENDPOINT` set it
exports spans, and nothing else. There are no OpenTelemetry metrics and no OpenTelemetry logs. This dashboard therefore
derives every number from spans, in two ways:

| Source | How | Good for | Limits |
|---|---|---|---|
| **Span metrics** (Prometheus) | Tempo's metrics generator counts spans and times them: `traces_spanmetrics_calls_total`, `traces_spanmetrics_latency_{sum,count,bucket}` with the labels `service`, `span_name`, `status_code` | Rates, error ratios, means (sum / count are exact at any length), "vs usual" tiles | The latency histogram stops at **16.4 s** (everything longer is in `+Inf`), and there are no span attributes |
| **TraceQL metrics** (Tempo) | `{ ... } \| rate()`, `count_over_time()`, `quantile_over_time(duration, ...)`, `avg_over_time(...)` computed on demand, optionally `by (span.<attribute>)` | Percentiles of runs, turns and startups (they last minutes), and every breakdown by a Paperclip attribute | Only recent data is kept in Tempo's metrics blocks; heavier than Prometheus |

Percentiles of anything long therefore come from TraceQL metrics, never from `histogram_quantile` (a unit test enforces
this), and ratio tiles use means.

Resource attributes: `service.name` (`OTEL_SERVICE_NAME`, default `paperclip`) and `service.version` (the built commit).
The dashboard's **Instance** variable lists every `service.name` that exports Paperclip spans.

Nothing is exported that identifies a person, a path or a prompt. Paperclip documents a closed attribute list: run IDs
are the first 12 hex characters of a SHA-256, and exception messages, paths, commands, arguments and content are dropped.
The one exception is the PostgreSQL auto-instrumentation, whose `db.statement` carries SQL text with placeholders (see
*Privacy and security* in the README).

## Spans the dashboard reads

### Native agent runs (`paperclip.native-runner`, schema v3)

```text
task.provider_session                      root of a run; links to the server's task.execution_attempt
├── heartbeat.queue
├── task.prepare ── environment.startup (environment.acquire, environment.workspace.realize), skills.prepare,
│                   heartbeat.prepare_before_environment, heartbeat.prepare_after_environment, native.coordinator.claim
├── native.session.execute
│   ├── runner.session.startup ── runner.transport.{connect,activation,ready}, runner.runtime.stage (stage.sync ...),
│   │                             runner.session.bootstrap | runner.session.resume, runner.turn.submit
│   └── agent.turn ── runner.turn.submitted_to_started, provider.time_to_first_agent_event,
│                     tool.request.input_stream, tool.execute
├── task.settle ── native.result.finalize, session.checkpoint.persist
└── task.time_to_first_token               cumulative: accepted trigger -> first deliverable text
```

A failed run or phase has an **error status** on its span; that is what every failure panel counts.

| Attribute | On | Used for |
|---|---|---|
| `paperclip.task.run.run_id` | roots, preparation | Run (hash) column in the run tables |
| `paperclip.task.run.runtime`, `.outcome`, `.wall_ms`, `.trace_schema_version` | `task.provider_session` | Run tables |
| `paperclip.native.span.provider` | `agent.turn` | Turns by provider (for ACPX, the underlying agent) |
| `paperclip.native.span.harness`, `.lifecycleMode`, `.bytesTransferred` | native session span | Sessions by harness and lifecycle, bytes transferred |
| `paperclip.native.span.operation` | `tool.execute`, `tool.request.input_stream` | Tools by operation (a known semantic name, or `other`) |
| `paperclip.native.span.eventKind`, `.duration_ms`, `.outcome` | `task.time_to_first_token`, others | `reasoning` or `agentMessage` first text |

### Server-side preparation and workspace (`paperclip.heartbeat-preparation`, `paperclip.execution`)

`task.execution_attempt`, `task.workspace_finalization`, `heartbeat.prepare.<phase>` (including `workspace_*` and
`configuration_*`), `workspace.*`, `workspace_sync.*`, `runtime_selection.*`, `runtime_context.*`, `skills.*`,
`connectors.*`, `completion.*`, `response.*`. Detail spans are capped at 16 per name per attempt. The dashboard reads the
main `workspace_sync.*` phases and `heartbeat.prepare.workspace*`, plus:

| Attribute | Meaning |
|---|---|
| `paperclip.execution.repositoryCache.outcome` | `disabled`, `hit`, `miss`, `published`, `already_present`, `contended`, `capacity`, `budget`, `invalid`, `error` |
| `paperclip.execution.repositoryCache.reference_supplied` | Whether a cache reference was supplied to the clone |
| `paperclip.execution.fileCount`, `paperclip.execution.bytes` | Non-negative integers on asset writes and verification |

### Controller (`paperclip.controller-startup`, `paperclip.native-reconciliation`)

`controller.startup.<phase>` (tool reviews, gateway sessions, delivery workers, accounting, plugin workers, native
recovery, hot-restart adoption, orphan reaping, scheduled retries, queued runs, goal recovery) and
`controller.native_reconciliation` with its phase children. Reconciliation passes are only recorded when they take one
second or more, with `paperclip.native_reconciliation.scoped` and `.candidates`.

### Budget (`paperclip.budgets`)

`budget.admission.{evaluate,reserve}`, `budget.accounting.{transaction,settlement,lock_wait,recover}`,
`budget.exposure.evaluate`, `budget.enforcement.{deliver,scope}`, `budget.cancellation.deliver`, with the attributes
`budget.policy_count` and `budget.enforcement.queue_delay_ms`.

### Task detail and chat

`issue.read.<phase>` (`paperclip.issue-read`, 23 phases) and `chat.slack.receipt` (`paperclip.chat`) with
`paperclip.chat.receipt.{operation,outcome,queue_ms,delivery_age_ms}`.

### Auto-instrumentation (`@opentelemetry/auto-instrumentations-node`)

HTTP, Express and PostgreSQL spans (the `fs`, `dns` and `net` instrumentations are disabled by Paperclip). The dashboard
reads server spans with `http.route` and PostgreSQL client spans with `db.system = "postgresql"`, `db.operation` and
`db.statement`. These attribute names follow the semantic-convention version of the installed instrumentation; if a
newer Paperclip moves to the stable names (`http.response.status_code`, `db.query.text`, ...), update the generator.

## Not in the dashboard

- **First-party usage telemetry** (anonymous, on by default, `PAPERCLIP_TELEMETRY_DISABLED=1` turns it off) goes to
  Paperclip's own service, not to OTLP.
- **Sentry** error monitoring is a separate opt-in path.
- **Agent CLI telemetry.** Paperclip can also point its Claude, Codex and OpenCode agents at an OTLP endpoint (logs and
  traces, with `paperclip.company.id` and `paperclip.agent.id` resource attributes). That is configured per agent in
  Paperclip, arrives under the agents' own service names, and is the Claude Code dashboard's territory.

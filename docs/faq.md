# FAQ

## Why not just use the Paperclip UI?

The UI shows you runs, costs and tasks. This keeps the *performance* history: how long runs, startups and first tokens
take over days, which preparation or workspace phase got slow, how the database and API behave, and trace waterfalls of
single runs. It also combines several Paperclip instances in one place.

## Paperclip only exports traces. Where do the metrics come from?

From the traces. Tempo turns spans into Prometheus *span metrics* (counts, error ratios, mean durations), and answers
*TraceQL metrics* queries for percentiles and breakdowns by span attribute. See
[`telemetry-reference.md`](telemetry-reference.md) for which panel uses which and why.

## Does anything leave my machine?

No, except the image download. Grafana listens on `127.0.0.1`, and Paperclip exports to the stack over a private Podman
network. Prompt, response and tool-argument content is not part of Paperclip's span attributes. See *Privacy and
security* in the README.

## Can I watch several Paperclip instances in one dashboard?

Yes. Give each a name with `OTEL_SERVICE_NAME` (`paperclip-otel/apply-paperclip-otel.py --service-name <name>`), point
them at the same stack and use the *Instance* variable.

## Can I use my own Grafana?

Yes. Import `dashboards/paperclip.json` (also attached to every release) under *Dashboards > New > Import*, or run
`GRAFANA_URL=... GRAFANA_PASSWORD=... python3 tools/import_dashboard.py`. It needs a Prometheus and a Tempo datasource
that receive Paperclip's OTLP data, with Tempo's **metrics generator** (span metrics) and **TraceQL metrics** enabled,
as in `grafana/otel-lgtm`. The dashboard picks the first datasource of each type; change `ds_prometheus` and `ds_tempo`
under *Dashboard settings > Variables* if you have several.

## Paperclip logs `the @opentelemetry/* packages are not installed`

Paperclip loads its OpenTelemetry SDK only when you install it, at the exact versions in its `server/package.json`. In a
container, build the image with `./install.sh --build-image <your image>` (the Containerfile reads the versions from that
image, so every Paperclip version works) and run Paperclip from it. On a host, `python3 paperclip-otel/peer-packages.py
<checkout>` prints the exact `pnpm add` line. If the message names a version mismatch, you installed other versions by
hand: reinstall the ones it expects.

## I already run Paperclip. Do I have to reinstall it?

No. Add the packages (see *Already running Paperclip?* in the README), three environment variables, and a collector it can
reach, then restart it. Your data, agents and configuration are untouched.

## Why are all the *Native runner* panels empty?

They only fill for agents with the `paperclip_runner` adapter. Agents on legacy adapters such as `claude_local` fill every
other row, because they all produce `task.execution_attempt` and its children. A native run additionally needs a task in
`standard`, `planning` or `ask` work mode, a Paperclip image built with `--target production`, and a credential the
runner accepts (`CLAUDE_CODE_OAUTH_TOKEN` or `ANTHROPIC_API_KEY` bound to the agent; the runner does not read the host's
Claude login). See *Troubleshooting* in the README for the two errors you meet when one of those is missing.

## A panel is empty or shows "none in this range"

Usually that is true: nothing of that kind happened in the range (no failed runs is good). If a panel should have data,
check *Spans per minute* in the Telemetry pipeline row, widen the time range, and compare
[`telemetry-reference.md`](telemetry-reference.md) with the spans in Tempo. Percentile panels need runs *in the range*;
run something, and note that Tempo only keeps recent data for TraceQL metrics.

## Why do some panels show an error when I pick 7 days?

Percentiles and the breakdowns by span attribute come from TraceQL metrics, and Tempo answers at most 24 hours per query
(`query_frontend.metrics.max_duration`, 24 h in `grafana/otel-lgtm`). Counts, rates, error ratios, the health tiles and the
trace tables use span metrics or searches and work on any range. For a longer view of a percentile, pick a 24 h window
and move it back in time, or raise the limit on a Tempo you run yourself.

## Why do durations in the health tiles use means, not percentiles?

Because those tiles divide "now" by "your usual last 7 days", which only PromQL can do, and span-metric percentiles
saturate at 16 s while agent runs take minutes. Means (sum / count) are exact at any length. The percentile panels
(TraceQL metrics) are in each section.

## How do I reset or wipe the data?

Stop the stack and delete its data: `~/.local/share/otel-lgtm` for the systemd install, or `docker compose down -v` for
the compose file. Then start it again.

## How do I change the Grafana password?

Log in with `admin` / `admin` and Grafana asks you to change it on first login.

## Which versions are tested?

See *Compatibility* in the README. Paperclip changes quickly and renames spans between versions; reports from other
versions are welcome.

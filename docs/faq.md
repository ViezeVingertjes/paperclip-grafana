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

Paperclip loads its OpenTelemetry SDK only when you install it, at the exact versions in its `server/package.json`.
Build the image with `./install.sh --build-image` (or the `paperclip-otel/Containerfile`), run Paperclip from it, and
restart. If it names a version mismatch, bump the versions in the Containerfile to the ones the message expects.

## A panel is empty or shows "none in this range"

Usually that is true: nothing of that kind happened in the range (no failed runs is good). If a panel should have data,
check *Spans per minute* in the Telemetry pipeline row, widen the time range, and compare
[`telemetry-reference.md`](telemetry-reference.md) with the spans in Tempo. Percentile panels need runs *in the range*;
run something, and note that Tempo only keeps recent data for TraceQL metrics.

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

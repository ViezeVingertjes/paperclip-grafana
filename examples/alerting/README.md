# Alert rule examples

Grafana alert rules in [file provisioning format](https://grafana.com/docs/grafana/latest/alerting/set-up/provision-alerting-resources/file-provisioning/) for four common cases:

| File | Fires when |
|---|---|
| [`run-failures.yaml`](run-failures.yaml) | An agent run failed in the last hour |
| [`controller-errors.yaml`](controller-errors.yaml) | A controller startup or recovery phase failed in the last hour |
| [`no-spans.yaml`](no-spans.yaml) | Paperclip exported no spans for 15 minutes |
| [`slow-first-token.yaml`](slow-first-token.yaml) | The mean time to first token over an hour is above 2 minutes |

All four use the span metrics Tempo derives from Paperclip's traces (they live in Prometheus, which is what alert rules
can query), so they need no extra setup beyond the stack.

## Using them

Each file is self-contained and provisions one alert rule into a `Paperclip` folder, next to the dashboard. Copy the
ones you want into Grafana's alerting provisioning path (by default `/etc/grafana/provisioning/alerting/`, or the
matching path under `~/.local/share/otel-lgtm` for this project's install) and restart or let Grafana reload it.

Before copying a file, open it and adjust:

- `datasourceUid`: the uid of your Prometheus datasource. Find it under *Connections > Data sources*; `grafana/otel-lgtm` uses `prometheus`.
- The service name (`service="paperclip"` is `OTEL_SERVICE_NAME`) and the threshold in the rule's `C` query.

These files deliberately have no contact point or notification policy, only a `severity` label:
wire that up yourself under *Alerting > Contact points* and *Notification policies*, or add a
matching label here and route on it.

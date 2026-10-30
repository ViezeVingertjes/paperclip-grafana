<div align="center">

# Paperclip Grafana

**See how fast your Paperclip agent runs start, answer and finish, and where the time goes.**
A local Grafana dashboard for [Paperclip](https://github.com/paperclipai/paperclip)'s OpenTelemetry traces: run health and duration, startup and first-token latency, agent turns and tools, workspace sync, controller recovery, budget checks, API and database performance, and **full trace waterfalls**. One command to install, everything stays on your machine.

[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
![Runs on](https://img.shields.io/badge/runs%20on-Podman%20%2B%20systemd%20or%20Docker-8A2BE2)
![Localhost only](https://img.shields.io/badge/network-localhost%20only-2ea44f)
[![Stars](https://img.shields.io/github/stars/ViezeVingertjes/paperclip-grafana?style=flat)](https://github.com/ViezeVingertjes/paperclip-grafana/stargazers)
[![Last commit](https://img.shields.io/github/last-commit/ViezeVingertjes/paperclip-grafana)](https://github.com/ViezeVingertjes/paperclip-grafana/commits/main)
[![CI](https://github.com/ViezeVingertjes/paperclip-grafana/actions/workflows/ci.yml/badge.svg)](https://github.com/ViezeVingertjes/paperclip-grafana/actions/workflows/ci.yml)

<img src="docs/screenshots/01-health-and-overview.jpg" alt="Health tiles and overview" width="900">

</div>

> **Unofficial.** This project is not affiliated with or endorsed by Paperclip. It reads telemetry that Paperclip itself emits.

## Highlights

- **Health at a glance.** Green, orange or red tiles that compare *now* with *your own* last 7 days (run failures, tool failures, run duration, time to first token, startup, preparation). No magic thresholds, so they fit any setup.
- **Runs, for any agent.** Throughput and failures, duration percentiles, average concurrent runs, recent, slowest and failed runs with a link to each trace. Built on the executor span every adapter emits.
- **Where run time goes.** Preparation phases, run configuration, skills, execution and completion, each broken down.
- **Native runner** (`paperclip_runner` agents). Time to first token, Runner startup, fresh versus resumed sessions, turn duration, tool executions, failures and latency per tool, turns by provider, sessions by harness.
- **Workspace.** Where workspace sync spends its time, the slowest preparation steps, repository checkout cache outcomes and data moved.
- **Controller, budget and chat.** Startup and recovery phases and their errors, budget admission and accounting (including lock waits), Slack receipt reactions.
- **API.** HTTP requests, latency and status codes by method, slowest requests, task-detail read phases.
- **Trace waterfalls.** Click a run and see every phase on a timeline.
- **Several instances.** Give each Paperclip an `OTEL_SERVICE_NAME` and filter or compare them with the *Instance* variable.
- **Easy to read.** Short names instead of raw span names, rates instead of raw counts so charts read the same at 15 minutes or 7 days, and a clear "none in this range" when there is nothing to show.

## Quick start

You need Linux with systemd, [Podman](https://podman.io/) 4.4 or newer, `curl` and `python3`, and a Paperclip image
(for example one built from the [Paperclip repository](https://github.com/paperclipai/paperclip) with
`podman build --target production ...`; see the note under [Troubleshooting](#troubleshooting)).
On Debian or Ubuntu: `sudo apt-get install -y podman curl python3`.
On macOS, Windows or without systemd, use [Docker Compose](#docker-compose) instead.

```bash
git clone https://github.com/ViezeVingertjes/paperclip-grafana.git
cd paperclip-grafana
./install.sh --build-image paperclip-local --paperclip-env /path/to/paperclip.env
```

Then run Paperclip **from the new `paperclip-otel` image on the `paperclip-net` network**, for example
`podman run -d --network paperclip-net --env-file /path/to/paperclip.env ... paperclip-otel`, and open
<http://127.0.0.1:3000>. Log in with `admin` / `admin` and **change the password**. The Paperclip dashboard is the home
page. The first start downloads the Grafana image, which can take a few minutes. The script waits for it.

Paperclip reads its OpenTelemetry settings at startup, so **restart it** after changing them. Check its log for
`[paperclip] OpenTelemetry service.version=<commit>`; a line saying the `@opentelemetry/*` packages are missing means it
is not running from the `paperclip-otel` image.

<details>
<summary>What <code>install.sh</code> does</summary>

1. Checks that Podman, systemd, curl and Python are available (clear message if not).
2. Installs a rootless **systemd user service** (`otel-lgtm.service`, a Podman Quadlet) that runs [`grafana/otel-lgtm`](https://github.com/grafana/docker-otel-lgtm): Grafana, Tempo (traces), Loki (logs), Prometheus (metrics) and an OpenTelemetry collector, bound to localhost, plus a Podman network `paperclip-net` that Paperclip joins.
3. Provisions the dashboard and removes the image's sample dashboards.
4. Enables *lingering* (`loginctl enable-linger`) so the stack starts at boot without a login. Skip with `--no-boot`.
5. With `--build-image [BASE]`: builds the `paperclip-otel` image from a Paperclip image, adding the exact-version OpenTelemetry packages Paperclip requires.
6. With `--paperclip-env FILE`: adds the export variables to that env file (a backup `FILE.bak-pre-otel` is made first).

It is safe to run again. See `./install.sh --help`.
</details>

## Already running Paperclip?

Nothing here needs a fresh Paperclip. You add three things to the one you have: the OpenTelemetry packages (Paperclip only
imports its SDK when they are installed, and only at the exact versions its `server/package.json` declares as
`peerDependencies`), three environment variables, and a collector that Paperclip can reach. Pick your setup:

<details>
<summary><b>Paperclip in a container (Podman or Docker)</b></summary>

```bash
./install.sh --build-image <your paperclip image>      # your image plus the packages, at the versions that image declares
./install.sh --paperclip-env /path/to/paperclip.env    # adds the three variables (or set them yourself, see below)
```

`paperclip-otel/Containerfile` reads the versions from *your* image, so any Paperclip version works, and builds with
`docker build` too (`PAPERCLIP_OTEL_PROTOCOL` or `--build-arg PROTOCOL=http/protobuf` picks another exporter). Run the new
`paperclip-otel` image instead of yours with these variables, on the same Podman network as the stack:

```text
OTEL_EXPORTER_OTLP_ENDPOINT=http://otel-lgtm:4317
OTEL_EXPORTER_OTLP_PROTOCOL=grpc
OTEL_SERVICE_NAME=paperclip
```

For a compose file, [`paperclip-otel/compose.override.example.yml`](paperclip-otel/compose.override.example.yml) is the whole
change. Restart Paperclip: the settings are read at startup.
</details>

<details>
<summary><b>Paperclip on the host (git checkout, <code>npx</code> or a package install)</b></summary>

```bash
python3 paperclip-otel/peer-packages.py /path/to/paperclip     # prints the exact `pnpm add ...` line for YOUR version
python3 paperclip-otel/apply-paperclip-otel.py /path/to/paperclip.env --endpoint http://127.0.0.1:4317
```

Run the printed `pnpm add` in the Paperclip checkout, load the env file the way you already start Paperclip, and restart it.
</details>

<details>
<summary><b>Your own Grafana, Tempo and Prometheus (or a collector you already run)</b></summary>

Point `OTEL_EXPORTER_OTLP_ENDPOINT` at your collector, then `./install.sh --import-dashboard http://your-grafana:3000`
(or import `dashboards/paperclip.json` in the UI). The dashboard needs a Prometheus and a Tempo datasource, with Tempo's
**metrics generator** (span metrics) and **TraceQL metrics** switched on, as in `grafana/otel-lgtm`. If you already run the
`otel-lgtm` stack from another setup, `./install.sh --join-network` puts it on the network Paperclip's container uses.
See [Using your own Grafana](#using-your-own-grafana).
</details>

**Check it works.** Paperclip logs `[paperclip] OpenTelemetry service.version=<commit>` at startup; a line saying the
`@opentelemetry/*` packages are missing or at the wrong version means it is not using them. In Grafana the
*Telemetry pipeline* row shows spans per minute within a minute of the first request.

**What fills in depends on your agents.** Every adapter (`claude_local`, `codex_local`, `paperclip_runner`, ...) fills the
Health, Runs, Run preparation, Execution, Workspace, Budget and API rows. The *Native runner* rows need `paperclip_runner`
agents, which also need a Claude credential the runner accepts and an image built from Paperclip's `production` target
(see [Troubleshooting](#troubleshooting)). Your own `OTEL_SERVICE_NAME` is fine: the *Instance* variable lists whatever
exports Paperclip spans.

## Screenshots

<table>
  <tr>
    <td width="50%"><a href="docs/screenshots/01-health-and-overview.jpg"><img src="docs/screenshots/01-health-and-overview.jpg" alt="Health and overview"></a><br><sub><b>Health and overview</b>: tiles that compare now with your own last 7 days turn green, orange or red.</sub></td>
    <td width="50%"><a href="docs/screenshots/02-runs.jpg"><img src="docs/screenshots/02-runs.jpg" alt="Runs"></a><br><sub><b>Runs</b>: throughput and failures, p50/p95 duration, average concurrency, and recent runs you can click through to the trace.</sub></td>
  </tr>
  <tr>
    <td width="50%"><a href="docs/screenshots/03-run-preparation.jpg"><img src="docs/screenshots/03-run-preparation.jpg" alt="Run preparation"></a><br><sub><b>Run preparation</b>: where the time before the agent starts goes, down to individual skill and configuration steps.</sub></td>
    <td width="50%"><a href="docs/screenshots/04-execution-and-completion.jpg"><img src="docs/screenshots/04-execution-and-completion.jpg" alt="Execution and completion"></a><br><sub><b>Execution and completion</b>: dispatch, runtime and the bookkeeping after a run, for every adapter.</sub></td>
  </tr>
  <tr>
    <td width="50%"><a href="docs/screenshots/05-native-startup-and-first-token.jpg"><img src="docs/screenshots/05-native-startup-and-first-token.jpg" alt="Native runner startup"></a><br><sub><b>Native runner: startup and first token</b>: time to first token, Runner startup, and a breakdown of the transport and session phases.</sub></td>
    <td width="50%"><a href="docs/screenshots/06-native-turns-and-tools.jpg"><img src="docs/screenshots/06-native-turns-and-tools.jpg" alt="Native runner turns and tools"></a><br><sub><b>Native runner: turns and tools</b>: turn duration, tool executions per tool, failures and latency.</sub></td>
  </tr>
  <tr>
    <td width="50%"><a href="docs/screenshots/07-workspace-and-providers.jpg"><img src="docs/screenshots/07-workspace-and-providers.jpg" alt="Workspace and environment"></a><br><sub><b>Providers and workspace</b>: where workspaces are realized, how the Runner is reached, the slowest preparation steps.</sub></td>
    <td width="50%"><a href="docs/screenshots/08-controller-and-budget.jpg"><img src="docs/screenshots/08-controller-and-budget.jpg" alt="Controller and budget"></a><br><sub><b>Controller and budget</b>: startup and recovery phases, and the cost of budget admission and accounting.</sub></td>
  </tr>
  <tr>
    <td width="50%"><a href="docs/screenshots/09-api.jpg"><img src="docs/screenshots/09-api.jpg" alt="API"></a><br><sub><b>API</b>: requests, latency and status codes, the slowest requests and the phases of a task-detail read.</sub></td>
    <td width="50%"><a href="docs/screenshots/10-trace-waterfall.jpg"><img src="docs/screenshots/10-trace-waterfall.jpg" alt="Trace waterfall"></a><br><sub><b>Trace waterfall</b>: one native run, from the queue through preparation and Runner startup to the agent turn.</sub></td>
  </tr>
</table>

## How it works

```mermaid
flowchart LR
  PC["Paperclip server<br/>(OpenTelemetry, traces only)"] -- "OTLP gRPC :4317<br/>over paperclip-net" --> C
  subgraph STACK ["otel-lgtm container (localhost only)"]
    direction TB
    C["OpenTelemetry collector"] --> T[("Tempo<br/>traces")]
    T -- "metrics generator" --> P[("Prometheus<br/>span metrics")]
    G["Grafana :3000"] --- P
    G --- T
  end
```

Paperclip sends **spans**: a trace per agent run (preparation, Runner startup, agent turns, tools, settlement), the
server's preparation and workspace phases, controller recovery, budget checks, and the HTTP and database spans from the
auto-instrumentation. Tempo stores them and generates span metrics; Grafana queries both.

### Paperclip only exports traces, so the numbers are derived

From the traces. Paperclip's OpenTelemetry support exports **spans and nothing else** (no metrics, no logs), so this
dashboard derives every number from them, in two ways that each fix the other's limit:

| | Span metrics (PromQL) | TraceQL metrics (Tempo) |
|---|---|---|
| **What** | Tempo counts and times spans into Prometheus series | Tempo computes `rate()`, `count_over_time()`, `quantile_over_time(duration, ...)` from stored spans on demand |
| **Used for** | Rates, error ratios, the health tiles ("vs usual"), alert rules | Every percentile of a run, turn or startup, and every breakdown by a Paperclip attribute (provider, tool, cache outcome, route ...) |
| **Limit** | Latency histogram stops at **16.4 s**; no span attributes | Only recent data; heavier to compute |

Agent runs last minutes, so percentiles can never come from the span-metric histogram. The health tiles use *means*
(sum / count, exact at any length) because "now divided by usual" needs PromQL. Details in
[`docs/telemetry-reference.md`](docs/telemetry-reference.md).

## How the colours work

Green, orange and red always mean *fine*, *watch this* and *act*; everything else stays neutral, so a colour always means something.

**The Health row** is not tied to one setup. Each tile compares the selected range with **your own last 7 days**:

| Tile | Rule |
|---|---|
| Run failure rate | failure share now / over 7 days, pulled toward your usual rate when the range holds only a few runs |
| Run duration, run configuration, workspace preparation, API latency | mean now / mean over 7 days. 1.00x = as usual |
| Failed runs, API server errors, controller errors | counts; a healthy setup has none, so any occurrence is orange |

Ratios turn orange at 1.5x and red at 2.5x of usual. With less than 7 days of history the baseline is just the data you
have, so tiles read about 1.00x until something changes. Adjust the steps in `tools/gen_dashboard.py` (`UP`, `ANY`, `BASE`).

**A few tiles use fixed lines** because "good" is the same for everyone: run success rate and tool success rate (orange
below 95%, red below 85%). Chart colours carry no health meaning: failed is red and OK green, p95 series are dashed.

## Customising the dashboard

`dashboards/paperclip.json` is generated. Edit [`tools/gen_dashboard.py`](tools/gen_dashboard.py) and regenerate; Grafana reloads the file within about 30 seconds (edits made in the Grafana UI are overwritten):

```bash
python3 tools/gen_dashboard.py > dashboards/paperclip.json
python3 tools/validate_dashboard.py --range 24h   # runs every query; also try 15m, 3h and 7d (at 7d, TraceQL metrics hit Tempo's 24 h limit and are reported as such)
```

The validator queries Grafana anonymously; set `GRAFANA_PASSWORD` if anonymous viewing is off. CI runs the same check on
every push: it starts the stack with `docker compose up -d`, feeds it with `tools/send_sample_telemetry.py` (Paperclip-shaped
sample traces, because there is no Paperclip in CI), and runs the validator against that, so a query that errors against a
live Grafana fails the build. **Never run the sample sender against a stack that holds your real telemetry.**

Charts are built to read the same at any range: counts and rates are expressed per hour or per minute (not per interval),
the minimum step is one minute (so a 15-minute view still has 15 points), and counts per fixed 5-minute step are titled as
such. The one hard limit is Tempo's 24 h cap on TraceQL metrics, which every affected panel mentions in its description.

Names and empty states are set in one block near the end of the script (`RENAMES`, `EMPTY_IS_GOOD`, `STAT_STEPS`), so a
new span name never means touching a query.

## Docker Compose

On macOS, Windows, or anywhere without systemd, use the compose file (Grafana stays on localhost):

```bash
docker compose up -d                                   # Grafana, Loki, Tempo, Prometheus and the collector
podman build -t paperclip-otel -f paperclip-otel/Containerfile --build-arg BASE=<your paperclip image> paperclip-otel
python3 paperclip-otel/apply-paperclip-otel.py /path/to/paperclip.env
```

Run Paperclip from `paperclip-otel` on the `paperclip-net` network the compose file creates.

## Using your own Grafana

Import [`dashboards/paperclip.json`](dashboards/paperclip.json) (also attached to every release) under *Dashboards > New >
Import*, or run `GRAFANA_URL=... GRAFANA_PASSWORD=... python3 tools/import_dashboard.py`. You need a Prometheus and a
Tempo datasource that receive Paperclip's OTLP data, with Tempo's **metrics generator** (span metrics) and **TraceQL
metrics** enabled, as in `grafana/otel-lgtm`. The dashboard picks the first datasource of each type; change
`ds_prometheus` and `ds_tempo` under *Dashboard settings > Variables* if you have several. An already running stack must
also share a network with Paperclip: `podman network connect paperclip-net otel-lgtm`.

## Alert examples

[`examples/alerting/`](examples/alerting/) has Grafana alert rules in provisioning format for four common cases: a
failed run, a failed controller phase, no spans for 15 minutes, and a slow time to first token. Copy the ones you want,
adjust the datasource uid, service name and threshold, and wire up a contact point; see that folder's README.

## Operating it

```bash
systemctl --user status otel-lgtm.service       # health
systemctl --user restart otel-lgtm.service
journalctl --user -u otel-lgtm.service -f       # logs
./install.sh --uninstall                        # removes the services, keeps your data
```

Data lives in `~/.local/share/otel-lgtm` (`docker compose down -v` for the compose install); delete it to wipe all stored telemetry. `python3 paperclip-otel/apply-paperclip-otel.py FILE --remove` takes the variables out of the env file again.

## Troubleshooting

| Symptom | Cause and fix |
|---|---|
| Dashboard is empty | Paperclip reads its OpenTelemetry settings at startup: restart it. Check the *Spans per minute* tile and Paperclip's log. |
| Paperclip logs "the @opentelemetry/* packages are not installed" | Run it from the `paperclip-otel` image (`./install.sh --build-image`), at the versions its `server/package.json` declares. |
| Paperclip cannot reach the collector | A container cannot use a port published on the host's `127.0.0.1`. Put both on `paperclip-net` and export to `http://otel-lgtm:4317`; for a stack started by something else, `podman network connect paperclip-net otel-lgtm`. |
| Percentile and breakdown panels show an error on long ranges | They come from TraceQL metrics, and Tempo answers at most **24 h** per query (`query_frontend.metrics.max_duration`; raise it on a Tempo you run yourself). Pick 24 h or less for those panels; counts, rates, health tiles and the trace tables work on any range. |
| Percentile panels are empty but counts are not | Percentiles come from TraceQL metrics, which only cover recent data; run something and look at a short range. |
| Counts and rates look short on a long range | `otel-lgtm` keeps about 15 days of metrics; the 7-day baseline in the health tiles needs that much history to be meaningful. |
| Native runner runs fail with `admission_installation` | You built Paperclip's last Dockerfile stage, the `cloud` variant, which adds a nested `/app/server/node_modules/.pnpm` and breaks the runner sidecar's provider-package lookup. Build with `--target production`, which is what Paperclip's own CI pins. |
| Native runner runs fail with `session_ensure_failed` | The native runner starts the agent in a sanitized environment and does not see the host's Claude login. Give the agent a credential it accepts: `CLAUDE_CODE_OAUTH_TOKEN` (a subscription token) or `ANTHROPIC_API_KEY`, through Paperclip's secrets or the agent's connection setup. |
| Stack does not start at boot | Lingering is off: run `sudo loginctl enable-linger $USER`. |
| "Port already in use" | Something else uses 3000, 4317 or 4318 on localhost. Free it and re-run `./install.sh`. |
| A *Native runner* panel is empty | Those spans only exist for agents with the `paperclip_runner` adapter, on a task in `standard`, `planning` or `ask` mode. Legacy adapters such as `claude_local` fill every other row. Detail spans are also capped at 16 per name per attempt. See [`telemetry-reference.md`](docs/telemetry-reference.md). |

## Privacy and security

- Everything listens on `127.0.0.1`. Nothing is sent anywhere, except the image download from Docker Hub. Paperclip reaches the stack over a private Podman network.
- Paperclip's spans carry a closed list of attributes: hashed run IDs, counts, durations and enumerated names. Prompts, responses, tool arguments, workspace paths and exception messages are not exported.
- The HTTP auto-instrumentation records the request path (`url.path`), which can contain task or agent IDs; the *Slowest API requests* panel shows it. Remove that column in `tools/gen_dashboard.py` if you do not want paths on screen.
- Grafana ships with `admin` / `admin`: change it on first login. No credentials are stored in this repository.

## Layout

| Path | Purpose |
|---|---|
| `install.sh` | Installs and uninstalls the Podman + systemd setup (`--help` lists the options) |
| `docker-compose.yml` | The Docker alternative |
| `dashboards/paperclip.json` | The generated dashboard |
| `tools/gen_dashboard.py` | **Source of truth** for the dashboard |
| `tools/validate_dashboard.py` | Runs every dashboard query at a chosen range |
| `tools/import_dashboard.py` | Imports the dashboard into an existing Grafana |
| `tools/send_sample_telemetry.py` | Pushes Paperclip-shaped sample traces, for CI only |
| `provisioning/`, `quadlet/` | Grafana dashboard provisioning, and the Podman service and network templates |
| `paperclip-otel/` | The Containerfile that adds Paperclip's OpenTelemetry packages (versions read from your image), `peer-packages.py` for host installs, the export variables, the script that merges them into an env file, and a compose override example |
| `tests/` | Unit tests (`python3 -m unittest discover -s tests -t .`) |
| `docs/` | [Telemetry reference](docs/telemetry-reference.md), [FAQ](docs/faq.md), [upgrade notes](docs/upgrading.md) |
| `examples/alerting/` | Grafana alert rule examples |
| `.github/` | CI, issue and pull request templates, and the contributing, security and conduct documents |
| `CHANGELOG.md` | What changed in each release |

## Compatibility

Tested with Paperclip `b31ec0a` (OpenTelemetry packages `sdk-node` 0.221.0, `auto-instrumentations-node` 0.79.0),
`grafana/otel-lgtm` 0.39.0 (Grafana 13.3, Tempo 3.1) and Podman 5.7. Paperclip renames spans between versions, so other
versions may leave panels empty. Issues and pull requests are welcome, especially reports from other versions.

## Contributing

Issues, ideas and pull requests are welcome; see [CONTRIBUTING](.github/CONTRIBUTING.md). Questions and "how do you use it" belong in [Discussions](https://github.com/ViezeVingertjes/paperclip-grafana/discussions). Security problems: [SECURITY](.github/SECURITY.md).

## License

[MIT](LICENSE)

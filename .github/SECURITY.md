# Security policy

## Scope

This project runs a local Grafana stack bound to `127.0.0.1`, a Containerfile that adds OpenTelemetry packages to a
Paperclip image, and a script that edits an env file. The things worth reporting are:

- anything that makes the stack reachable from outside the machine
- the installer or env-file script changing files outside what the README documents
- the env-file script printing, logging or copying secrets from the file it edits
- telemetry content (prompts, responses, identifiers, SQL text) being exported or shown when it should not be

Paperclip itself, and Grafana, Loki, Tempo, Prometheus and the OpenTelemetry collector, are separate projects: report
problems in [`paperclipai/paperclip`](https://github.com/paperclipai/paperclip) and in
[`grafana/otel-lgtm`](https://github.com/grafana/docker-otel-lgtm) upstream.

## Reporting

Please do not open a public issue. Use GitHub's private
[security advisory form](https://github.com/ViezeVingertjes/paperclip-grafana/security/advisories/new).
You should get a first reply within a week.

## Supported versions

Only the latest release and `main`.

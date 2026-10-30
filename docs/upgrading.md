# Upgrading

The dashboard is a generated file and Grafana reloads it within about 30 seconds, so most upgrades are just
`git pull`. Restart the Grafana container when the notes below say so, because provisioning settings and the image tag
are only read at startup.

```bash
git pull
systemctl --user restart otel-lgtm      # Podman + systemd install
docker compose pull && docker compose up -d   # compose install
```

Edits you made to the dashboard in the Grafana UI are overwritten by the file. Copy them into
`tools/gen_dashboard.py` (see *Customising the dashboard*) or save the dashboard under another name first.

## Upgrading Paperclip

Paperclip refuses any OpenTelemetry package at a version other than the one in its `server/package.json`
`peerDependencies` (it logs one line and runs without tracing). After pulling or installing a new Paperclip:

1. Rebuild the OpenTelemetry image from the new Paperclip image with `./install.sh --build-image <new image>`; the
   Containerfile reads the versions from that image, so nothing to edit. On a host, run
   `python3 paperclip-otel/peer-packages.py <checkout>` and re-run the `pnpm add` it prints.
2. Compare `doc/observability.md` in Paperclip with `docs/telemetry-reference.md`; spans are renamed between versions.

## Notes by version

### 1.0.0
- First release.

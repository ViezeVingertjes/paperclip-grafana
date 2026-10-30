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
`peerDependencies` (it logs one line and runs without tracing). After pulling a new Paperclip:

1. Compare `peerDependencies` there with the versions in `paperclip-otel/Containerfile`.
2. Update the Containerfile if they moved, and rebuild with `./install.sh --build-image`.
3. Compare `doc/observability.md` with `docs/telemetry-reference.md`; spans are renamed between versions.

## Notes by version

### 1.0.0
- First release.

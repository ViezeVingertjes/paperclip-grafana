#!/usr/bin/env bash
# Local Grafana dashboard for Paperclip telemetry, running in rootless Podman under systemd.
# Run ./install.sh --help for the options.
set -euo pipefail

here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
quadlet_dir="$HOME/.config/containers/systemd"
data_dir="$HOME/.local/share/otel-lgtm"

usage() {
  cat <<'USAGE'
Usage: ./install.sh [options]

Installs a Grafana stack (Grafana, Tempo, Loki, Prometheus) as a rootless Podman container managed by systemd,
with the "Paperclip" dashboard. Everything listens on localhost only. The stack joins a Podman network called
paperclip-net, which a Paperclip container joins too, so it can export traces to http://otel-lgtm:4317.

Options:
  --paperclip-env FILE   Add the OpenTelemetry variables to a Paperclip env file (a backup is made first)
  --build-image [BASE]   Build the "paperclip-otel" image: the Paperclip image BASE (default paperclip-local) plus the
                         OpenTelemetry packages Paperclip needs before it will export anything
  --join-network         For a stack that is already installed (by this script or another setup): add the paperclip-net
                         network to its otel-lgtm unit and restart it. A running rootless Podman container cannot be
                         attached to a bridge network, so Paperclip could not otherwise reach http://otel-lgtm:4317
  --import-dashboard [URL]
                         Import the dashboard into the Grafana at URL (default http://127.0.0.1:3000), for example one that
                         this script did not install. Set GRAFANA_PASSWORD if anonymous editing is off
  --no-boot              Do not enable lingering (the stack then starts when you log in instead of at boot)
  --uninstall            Stop and remove the services (stored data is kept in ~/.local/share/otel-lgtm)
  -h, --help             Show this help

Options can be combined, and the script can be re-run safely. PAPERCLIP_OTEL_PROTOCOL (grpc, http/protobuf or http/json)
chooses the exporter that --build-image installs; it must match OTEL_EXPORTER_OTLP_PROTOCOL.
USAGE
}

env_file=""; build_image=0; base_image="paperclip-local"; boot=1; uninstall=0; join_network=0; import_url=""
while (( $# )); do
  case "$1" in
    --paperclip-env) env_file="${2:?--paperclip-env needs a file}"; shift ;;
    --build-image) build_image=1; if [[ "${2:-}" != "" && "${2:-}" != --* ]]; then base_image="$2"; shift; fi ;;
    --join-network) join_network=1 ;;
    --import-dashboard) import_url="http://127.0.0.1:3000"; if [[ "${2:-}" != "" && "${2:-}" != --* ]]; then import_url="$2"; shift; fi ;;
    --no-boot) boot=0 ;;
    --uninstall) uninstall=1 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown option: $1" >&2; usage >&2; exit 2 ;;
  esac
  shift
done

if (( uninstall )); then
  systemctl --user stop otel-lgtm.service 2>/dev/null || true
  rm -f "$quadlet_dir/otel-lgtm.container" "$quadlet_dir/paperclip-net.network"
  systemctl --user daemon-reload
  echo "Removed the services. Data is kept in $data_dir (delete it to wipe all stored telemetry)."
  echo "Paperclip's env file is untouched; run  python3 paperclip-otel/apply-paperclip-otel.py FILE --remove  to undo it."
  exit 0
fi

# ---- standalone actions for a stack that already exists ----------------------------------------------------------
if [[ -n "$import_url" ]]; then
  command -v python3 >/dev/null || { echo "python3 is required" >&2; exit 1; }
  [[ -f "$here/dashboards/paperclip.json" ]] || python3 "$here/tools/gen_dashboard.py" > "$here/dashboards/paperclip.json"
  GRAFANA_URL="$import_url" python3 "$here/tools/import_dashboard.py"
  exit 0
fi

if (( join_network )); then
  unit="$quadlet_dir/otel-lgtm.container"
  [[ -f "$unit" ]] || { echo "No installed otel-lgtm unit at $unit. Run ./install.sh without --join-network to install the stack." >&2; exit 1; }
  cp "$here/quadlet/paperclip-net.network" "$quadlet_dir/paperclip-net.network"
  if grep -q '^Network=paperclip-net.network' "$unit" && podman inspect otel-lgtm --format '{{range $k,$v := .NetworkSettings.Networks}}{{$k}} {{end}}' 2>/dev/null | grep -q paperclip-net; then
    echo "otel-lgtm already joins paperclip-net; nothing to do."
    exit 0
  fi
  if ! grep -q '^Network=paperclip-net.network' "$unit"; then
    cp -p "$unit" "$unit.bak-pre-paperclip"    # the original is kept next to it
    sed -i '/^ContainerName=otel-lgtm$/a Network=paperclip-net.network' "$unit"
    grep -q '^Network=paperclip-net.network' "$unit" || { echo "Could not add the network to $unit; add 'Network=paperclip-net.network' to its [Container] section by hand." >&2; exit 1; }
  fi
  systemctl --user daemon-reload
  systemctl --user restart otel-lgtm.service
  echo -n "Waiting for Grafana"
  for _ in $(seq 1 60); do curl -sf -o /dev/null http://127.0.0.1:3000/api/health && break; echo -n "."; sleep 2; done
  echo
  if podman inspect otel-lgtm --format '{{range $k,$v := .NetworkSettings.Networks}}{{$k}} {{end}}' | grep -q paperclip-net; then
    echo "otel-lgtm is on paperclip-net: Paperclip can export to http://otel-lgtm:4317."
  else
    echo "otel-lgtm is not on paperclip-net; check: systemctl --user status otel-lgtm.service" >&2
    exit 1
  fi
  exit 0
fi

# ---- preflight: fail early with a clear message --------------------------------------------------------------
missing=()
for cmd in podman systemctl curl python3; do command -v "$cmd" >/dev/null || missing+=("$cmd"); done
if (( ${#missing[@]} )); then
  echo "Missing required tools: ${missing[*]}" >&2
  echo "On Debian/Ubuntu: sudo apt-get install -y podman curl python3   (systemd is required too)" >&2
  exit 1
fi
if ! systemctl --user show-environment >/dev/null 2>&1; then
  echo "systemd user services are not available in this session (no user bus)." >&2
  echo "Log in through a normal session, or use docker-compose.yml instead (see the README)." >&2
  exit 1
fi
if (( $(podman --version | sed -E 's/[^0-9]*([0-9]+).*/\1/') < 4 )); then
  echo "Podman 4.4 or newer is required (Quadlet support); found: $(podman --version)" >&2
  exit 1
fi
for port in 3000 4317 4318; do
  if ss -ltn 2>/dev/null | grep -q "127.0.0.1:$port " && ! podman ps --format '{{.Names}}' | grep -qx otel-lgtm; then
    echo "Port $port on localhost is already in use by something else; free it and re-run." >&2
    exit 1
  fi
done

[[ -f "$here/dashboards/paperclip.json" ]] || python3 "$here/tools/gen_dashboard.py" > "$here/dashboards/paperclip.json"

# ---- Grafana stack as a systemd user service (Podman Quadlet) -------------------------------------------------
mkdir -p "$quadlet_dir" "$data_dir"
sed "s|@SETUP_DIR@|$here|g" "$here/quadlet/otel-lgtm.container.in" > "$quadlet_dir/otel-lgtm.container"
cp "$here/quadlet/paperclip-net.network" "$quadlet_dir/paperclip-net.network"
if ! systemctl --user is-active --quiet otel-lgtm.service; then
  podman rm -f otel-lgtm >/dev/null 2>&1 || true    # a container started by hand would clash with the service's name
fi
systemctl --user daemon-reload
systemctl --user restart otel-lgtm.service

# A rootless service starts at boot (without a login) only if lingering is enabled for the user.
if (( boot )) && [[ "$(loginctl show-user "$USER" -p Linger --value 2>/dev/null)" != "yes" ]]; then
  loginctl enable-linger "$USER" 2>/dev/null || echo "NOTE: run 'sudo loginctl enable-linger $USER' so the stack starts at boot."
fi

echo -n "Waiting for Grafana (the first start pulls the image, which can take a few minutes)"
ready=0
for _ in $(seq 1 150); do
  if curl -sf -o /dev/null http://127.0.0.1:3000/api/health; then ready=1; break; fi
  echo -n "."; sleep 2
done
echo
if (( ! ready )); then
  echo "Grafana did not come up in time. Check: systemctl --user status otel-lgtm.service   and   podman logs otel-lgtm" >&2
  exit 1
fi

# ---- optional parts ---------------------------------------------------------------------------------------------
if (( build_image )); then
  # Paperclip's Dockerfile ends with a "cloud" stage that adds a nested /app/server/node_modules/.pnpm, which breaks the
  # native Runner's provider-package lookup (admission_installation). The default image is the "production" target.
  if podman run --rm --entrypoint sh "$base_image" -c 'test -d /app/server/node_modules/.pnpm' 2>/dev/null; then
    echo "WARNING: $base_image has /app/server/node_modules/.pnpm, so it is Paperclip's 'cloud' stage." >&2
    echo "         Native runner runs will fail with admission_installation. Rebuild it with: podman build --target production ..." >&2
  fi
  podman build -t paperclip-otel -f "$here/paperclip-otel/Containerfile" --build-arg "BASE=$base_image" \
    --build-arg "PROTOCOL=${PAPERCLIP_OTEL_PROTOCOL:-grpc}" "$here/paperclip-otel"
  echo "Built the paperclip-otel image from $base_image. Run Paperclip from it, on the paperclip-net network (see README)."
fi

if [[ -n "$env_file" ]]; then python3 "$here/paperclip-otel/apply-paperclip-otel.py" "$env_file"; fi

cat <<MSG

Done.
  Grafana   http://127.0.0.1:3000   (first login: admin / admin, change the password right away)
  OTLP      grpc 127.0.0.1:4317    http 127.0.0.1:4318    from containers on paperclip-net: http://otel-lgtm:4317
  Status    systemctl --user status otel-lgtm.service
MSG
if [[ -z "$env_file" ]]; then
  echo "  Next      ./install.sh --build-image --paperclip-env <env file>   (see the README)"
fi
echo "  Then      restart Paperclip; the OpenTelemetry settings are read at startup."

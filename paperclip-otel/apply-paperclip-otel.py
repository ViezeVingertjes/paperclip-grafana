#!/usr/bin/env python3
"""Merge paperclip-telemetry-env.json into a dotenv file that Paperclip reads (for example the env file you pass to
`podman run --env-file`), so the server starts exporting traces.

Backs the file up first (<file>.bak-pre-otel, only if no backup exists yet) and leaves every other line untouched.
Use --remove to take the keys out again.

  apply-paperclip-otel.py ENV_FILE [--endpoint URL] [--service-name NAME] [--protocol grpc|http/protobuf|http/json] [--remove]

Defaults: endpoint http://otel-lgtm:4317 (the stack's container name on a shared Podman network; use
http://127.0.0.1:4317 when Paperclip runs on the host), service name paperclip (CLAUDE-style: set PAPERCLIP_SERVICE_NAME
or --service-name to tell several instances apart; the dashboard's Instance variable lists them).
"""
import argparse, json, os, shutil, sys

here = os.path.dirname(os.path.abspath(__file__))
KEYS = json.load(open(os.path.join(here, "paperclip-telemetry-env.json")))


def apply(lines, values, remove):
    """Return the dotenv lines with KEYS set to values (or removed). Order and unrelated lines are kept."""
    seen, out = set(), []
    for line in lines:
        key = line.split("=", 1)[0].strip() if "=" in line and not line.lstrip().startswith("#") else None
        if key in KEYS:
            seen.add(key)
            if not remove:
                out.append(f"{key}={values[key]}")
            continue
        out.append(line)
    if not remove:
        out += [f"{k}={values[k]}" for k in KEYS if k not in seen]
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("env_file")
    ap.add_argument("--endpoint", default=KEYS["OTEL_EXPORTER_OTLP_ENDPOINT"])
    ap.add_argument("--protocol", default=KEYS["OTEL_EXPORTER_OTLP_PROTOCOL"], choices=["grpc", "http/protobuf", "http/json"])
    ap.add_argument("--service-name", default=os.environ.get("PAPERCLIP_SERVICE_NAME") or KEYS["OTEL_SERVICE_NAME"])
    ap.add_argument("--remove", action="store_true")
    a = ap.parse_args(argv)
    values = {"OTEL_EXPORTER_OTLP_ENDPOINT": a.endpoint, "OTEL_EXPORTER_OTLP_PROTOCOL": a.protocol, "OTEL_SERVICE_NAME": a.service_name}
    lines = open(a.env_file).read().splitlines() if os.path.exists(a.env_file) else []
    if os.path.exists(a.env_file) and not os.path.exists(a.env_file + ".bak-pre-otel"):
        shutil.copy2(a.env_file, a.env_file + ".bak-pre-otel")
        os.chmod(a.env_file + ".bak-pre-otel", os.stat(a.env_file).st_mode & 0o777)   # the env file holds secrets: keep its mode
    out = apply(lines, values, a.remove)
    with open(a.env_file, "w") as f:
        f.write("\n".join(out) + "\n")
    print(("removed from " if a.remove else "updated ") + a.env_file)


if __name__ == "__main__":
    sys.exit(main())

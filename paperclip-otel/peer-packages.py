#!/usr/bin/env python3
"""Print the OpenTelemetry packages a Paperclip needs, at the exact versions it declares, and how to install them.

For a Paperclip that is NOT in a container image you build with paperclip-otel/Containerfile: a git checkout, `npx`
or a package install. Paperclip refuses any other version than the ones in its server/package.json `peerDependencies`
(it then logs one line and exports nothing), so read them from the Paperclip you actually run.

  peer-packages.py [PATH] [--protocol grpc|http/protobuf|http/json] [--json]

PATH is a Paperclip checkout, its server directory, or a server/package.json (default: the current directory).
"""
import argparse, json, os, sys

EXPORTERS = {"grpc": "grpc", "http/protobuf": "proto", "http/json": "http"}
COMMON = ["sdk-node", "auto-instrumentations-node", "resources", "semantic-conventions"]


def manifest_path(path):
    """Find server/package.json from a checkout, a server directory or the file itself."""
    for candidate in (path, os.path.join(path, "package.json"), os.path.join(path, "server", "package.json")):
        if os.path.isfile(candidate) and os.path.basename(candidate) == "package.json":
            with open(candidate) as f:
                if "peerDependencies" in json.load(f) or "server" in candidate:
                    return candidate
    raise SystemExit(f"no server/package.json with peerDependencies found under {path}")


def packages(manifest, protocol):
    """The exact name@version list for a protocol, from the manifest's peerDependencies."""
    if protocol not in EXPORTERS:
        raise SystemExit("protocol must be grpc, http/protobuf or http/json")
    with open(manifest) as f:
        peers = json.load(f).get("peerDependencies") or {}
    wanted = [f"@opentelemetry/{n}" for n in COMMON + [f"exporter-trace-otlp-{EXPORTERS[protocol]}"]]
    missing = [n for n in wanted if n not in peers]
    if missing:
        raise SystemExit("this Paperclip does not declare: " + ", ".join(missing) + " (OpenTelemetry may not be supported in this version)")
    return {n: peers[n] for n in wanted}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("path", nargs="?", default=".")
    ap.add_argument("--protocol", default="grpc", choices=list(EXPORTERS))
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    manifest = manifest_path(a.path)
    pkgs = packages(manifest, a.protocol)
    if a.json:
        print(json.dumps(pkgs, indent=2))
        return 0
    specs = " ".join(f"{n}@{v}" for n, v in pkgs.items())
    print(f"Paperclip manifest: {manifest}\n")
    print("Install these exact versions next to the Paperclip server (from the checkout root):\n")
    print(f"  pnpm add {specs}\n")
    print("Then set, for the Paperclip process (see apply-paperclip-otel.py for an env file):\n")
    print("  OTEL_EXPORTER_OTLP_ENDPOINT=http://127.0.0.1:4317   # the collector's address from where Paperclip runs")
    print(f"  OTEL_EXPORTER_OTLP_PROTOCOL={a.protocol}")
    print("  OTEL_SERVICE_NAME=paperclip\n")
    print("and restart Paperclip. It logs `[paperclip] OpenTelemetry service.version=<commit>` when tracing started.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

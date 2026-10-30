#!/usr/bin/env python3
"""Import dashboards/paperclip.json into an existing Grafana (into a "Paperclip" folder), overwriting the previous version.

  GRAFANA_URL=http://127.0.0.1:3000 [GRAFANA_PASSWORD=...] tools/import_dashboard.py [dashboard.json]

Uses GRAFANA_PASSWORD (user admin, or GRAFANA_USER) from the environment when set (never stored in files); otherwise the
request is anonymous, which works when anonymous editing is enabled, as in grafana/otel-lgtm. The dashboard is saved in
Grafana's database, so it survives restarts but is not reloaded from the file: run this again after regenerating it.
"""
import base64, json, os, sys, urllib.error, urllib.request

if any(a in ("-h", "--help") for a in sys.argv[1:]):
    sys.exit(__doc__)
G = os.environ.get("GRAFANA_URL", "http://127.0.0.1:3000").rstrip("/")
user = os.environ.get("GRAFANA_USER", "admin")
auth = "Basic " + base64.b64encode(f"{user}:{os.environ['GRAFANA_PASSWORD']}".encode()).decode() if "GRAFANA_PASSWORD" in os.environ else None
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
path = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "dashboards", "paperclip.json")


def call(method, url, body=None):
    headers = {"Content-Type": "application/json"}
    if auth:
        headers["Authorization"] = auth
    req = urllib.request.Request(G + url, data=json.dumps(body).encode() if body is not None else None, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, json.load(r)
    except urllib.error.HTTPError as e:
        return e.code, {"message": e.read().decode()[:300]}


dashboard = json.load(open(path))
dashboard["id"] = None
# The folder is found by its title (provisioning creates it the same way), and Grafana assigns its uid.
status, folders = call("GET", "/api/folders")
folder = next((f for f in folders if f.get("title") == "Paperclip"), None) if status < 300 else None
if folder is None:
    status, folder = call("POST", "/api/folders", {"title": "Paperclip"})
    if status >= 300:
        sys.exit(f"could not create the Paperclip folder: HTTP {status} {folder.get('message')}")
FOLDER = folder["uid"]
status, body = call("POST", "/api/dashboards/db", {"dashboard": dashboard, "folderUid": FOLDER, "overwrite": True, "message": "tools/import_dashboard.py"})
if status >= 300:
    sys.exit(f"import failed: HTTP {status} {body.get('message')}")
print(f"imported {dashboard['title']!r}: {G}{body['url']}")

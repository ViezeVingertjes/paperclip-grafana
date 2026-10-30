#!/usr/bin/env python3
"""Run every query of dashboards/paperclip.json against Grafana's datasources and report results.
Uses GRAFANA_PASSWORD from the environment when set (never stored in files); otherwise queries run anonymously.

  tools/validate_dashboard.py [dashboard.json] [--range 15m|3h|24h|7d]   (default 3h; use several ranges to check scaling)

Prometheus queries run as range queries, TraceQL searches as Tempo searches, and TraceQL metrics queries (the rate,
count and quantile panels) through Tempo's metrics endpoints, exactly the calls Grafana makes for the panels.
"""
import base64, json, os, sys, time, urllib.error, urllib.parse, urllib.request
G = os.environ.get("GRAFANA_URL", "http://127.0.0.1:3000")
# Without GRAFANA_PASSWORD the queries run anonymously, which works when anonymous viewing is enabled.
auth = "Basic " + base64.b64encode(f"admin:{os.environ['GRAFANA_PASSWORD']}".encode()).decode() if "GRAFANA_PASSWORD" in os.environ else None
args = [a for a in sys.argv[1:] if not a.startswith("--")]
rng = sys.argv[sys.argv.index("--range") + 1] if "--range" in sys.argv else "3h"
args = [a for a in args if a != rng]
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
d = json.load(open(args[0] if args else os.path.join(ROOT, "dashboards", "paperclip.json")))
secs = {"m": 60, "h": 3600, "d": 86400}[rng[-1]] * int(rng[:-1])
now = int(time.time()); start = now - secs
# Grafana picks roughly range / 600 points, never finer than 15 s; the rate interval is at least 4x the step
step = max(15, secs // 600)
sub = {"$__interval_ms": str(step * 1000), "$__rate_interval_ms": str(max(step * 4, 60) * 1000), "$__rate_interval": f"{max(step * 4, 60)}s",
       "$__interval": f"{step}s", "$__auto": f"{step}s", "$__range": rng, "${service:regex}": ".*", "$service": ".*"}


def fix(s):
    for k, v in sorted(sub.items(), key=lambda kv: -len(kv[0])):
        s = s.replace(k, v)
    return s


def get(path, params):
    req = urllib.request.Request(G + path + "?" + urllib.parse.urlencode(params), headers={"Authorization": auth} if auth else {})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        return {"status": "error", "error": e.read().decode()[:300]}


def walk(panels):
    """Every panel, including the ones inside collapsed rows."""
    for p in panels:
        yield p
        yield from walk(p.get("panels", []))


bad = 0
limited = []   # TraceQL metrics queries Tempo refuses because the range is over its limit (24 h by default)
empty = []
for p in walk(d["panels"]):
    for t in p.get("targets", []):
        ds = t["datasource"]["type"]; q = fix(t.get("expr") or t.get("query", "")); t0 = time.time()
        if ds == "prometheus":
            r = get("/api/datasources/proxy/uid/prometheus/api/v1/query_range", {"query": q, "start": start, "end": now, "step": step})
            ok = r.get("status") == "success"; n = len(r["data"]["result"]) if ok else r.get("error")
        elif t.get("metricsQueryType"):   # TraceQL metrics: Tempo computes the series
            path = "/api/metrics/query_range" if t["metricsQueryType"] == "range" else "/api/metrics/query"
            r = get("/api/datasources/proxy/uid/tempo" + path, {"q": q, "start": start, "end": now, "step": t.get("step") or f"{max(step, 300)}s"})
            ok = "error" not in r and r.get("status") != "error"; n = len(r.get("series", [])) if ok else r.get("error")
        else:   # TraceQL search
            r = get("/api/datasources/proxy/uid/tempo/api/search", {"q": q, "start": start, "end": now, "limit": 5})
            ok = "error" not in r and "status" not in r; n = len(r.get("traces", [])) if ok else r.get("error")
        if not ok and "exceeds the maximum allowed duration" in str(n):
            limited.append(p["title"]); print(f"lim    -   {time.time() - t0:5.1f}s  [{ds[:4]}] {p['title'][:48]}  (Tempo range limit)"); continue
        flag = "ok " if ok else "ERR"
        if not ok:
            bad += 1
        elif n == 0:
            empty.append(p["title"])
        print(f"{flag} {str(n):>4} {time.time() - t0:5.1f}s  [{ds[:4]}] {p['title'][:48]}" + ("" if ok else f"\n      {n}"))
print("FAILED:", bad)
if limited:
    print(f"{len(limited)} TraceQL metrics queries are over Tempo's range limit at {rng} (not failures: pick 24h or less for those panels)")
if empty:
    print(f"{len(empty)} queries returned no series (fine for panels that only fill when something happens, e.g. failures)")
sys.exit(1 if bad else 0)

# Contributing

Issues and pull requests are welcome.

## Changing the dashboard

`dashboards/paperclip.json` is generated. Edit [`tools/gen_dashboard.py`](../tools/gen_dashboard.py), regenerate and
validate against a running stack that receives telemetry from a real Paperclip:

```bash
python3 tools/gen_dashboard.py > dashboards/paperclip.json
python3 tools/validate_dashboard.py --range 24h   # also try 15m, 3h and 7d
```

Grafana reloads the file within about 30 seconds. Edits made in the Grafana UI are overwritten, so do not rely on them.

Paperclip exports traces only, so every number on the dashboard is derived from spans: span metrics (PromQL) for rates,
error ratios and means, and TraceQL metrics for percentiles and anything grouped by a span attribute. Say which one a new
panel uses and why; the header of `tools/gen_dashboard.py` explains the trade-off (span-metric histograms stop at 16 s).

## Checks

CI runs these, and so can you. The tests need only the Python standard library:

```bash
python3 -m unittest discover -s tests -t .   # unit tests, plus "dashboards/paperclip.json matches the generator"
pip install ruff yamllint && ruff check . && yamllint .
shellcheck install.sh
```

CI also starts the stack, sends it `tools/send_sample_telemetry.py` (Paperclip-shaped sample traces; there is no Paperclip in
CI) and runs the validator, so a query that errors against a live Grafana fails the build. Never run the sample sender
against a stack that holds your real telemetry.

## Pull requests

- Keep one change per pull request and explain what it fixes or adds.
- Commit the regenerated `dashboards/paperclip.json` together with the generator change.
- If you read a new span or attribute, add it to `tools/send_sample_telemetry.py` and `docs/telemetry-reference.md`; a test fails otherwise.
- If a panel changes visibly, refresh the matching screenshot in `docs/screenshots/` and make sure it shows no account details.
- Do not add credentials, tokens or real identifiers anywhere.

## Reporting problems

Use the issue templates. For security problems see [SECURITY.md](SECURITY.md).

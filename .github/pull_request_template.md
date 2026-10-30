## What changed and why

## Checklist

- [ ] Edited `tools/gen_dashboard.py` and regenerated `dashboards/paperclip.json`
- [ ] `python3 tools/validate_dashboard.py` reports `FAILED: 0` against a stack fed by a real Paperclip
- [ ] New spans or attributes are in `tools/send_sample_telemetry.py` and `docs/telemetry-reference.md`
- [ ] Screenshots show no account details

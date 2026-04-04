Run the full stress test suite (200 seeds x 2 player orders) and report results.

Run:
```bash
python3 -m pytest tests/integration/test_stress.py -v --tb=short 2>&1
```

Report:
- Total pass/fail count
- Any failures with seed numbers and error summaries
- If all pass, just say "200 stress tests passing in Xs"

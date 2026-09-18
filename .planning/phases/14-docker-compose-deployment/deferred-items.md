# Deferred Items — Phase 14

Out-of-scope discoveries logged per execution scope-boundary rule (not fixed,
not caused by the plans that found them).

## 14-04: Empty-string BIOCLAW_WEB_PASSWORD authenticates (auth bypass)

**Found during:** Task 1, while reasoning about what Compose's `${VAR}`
interpolation does with an unset variable.

**Symptom:** `webapp/backend/auth.py::_valid()` guards only the `None` case:

```python
expected = os.environ.get("BIOCLAW_WEB_PASSWORD")
if expected is None or password is None:
    return False
return secrets.compare_digest(password, expected)
```

If `BIOCLAW_WEB_PASSWORD` is set to an empty string, `expected == ""` (not
None), and `secrets.compare_digest("", "")` returns True. A request carrying an
explicitly empty password — `GET /api/...?password=` — authenticates. Confirmed
live.

This is reachable outside Docker too: `BIOCLAW_WEB_PASSWORD="" uv run uvicorn ...`
starts an instance that anyone can log into.

**Mitigated at the Compose layer only:** `docker-compose.yml` uses
`${BIOCLAW_WEB_PASSWORD:?...}`, so Compose refuses to start when the var is
unset or empty. That closes the Docker path — which mattered, because
`.env.example` ships the value blank and the documented flow is "copy and fill
in". It does not fix the underlying function.

**Action:** Not fixed — `webapp/backend/auth.py` is not in 14-04's
`files_modified`. A follow-up plan should change the guard to
`if not expected or password is None:` and add a regression test asserting that
an empty expected password rejects every candidate, including `""`.

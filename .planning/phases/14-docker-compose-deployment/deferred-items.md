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

**Action:** RESOLVED 2026-09-18, immediately after 14-04, at Darren's direction.
Guard changed to `if not expected or not password:` in `webapp/backend/auth.py`,
with `tests/test_auth_blank_password.py` (15 tests) covering both
`require_password` and `require_password_ws` across every empty-credential
combination, plus a normal-path regression check.

**Correction to the writeup above.** The vector originally named — an empty
`?password=` query param, as stated in 14-04-SUMMARY.md and commit 9920b5a — is
NOT reachable. `candidate = candidate or password or session` returns its LAST
operand when all are falsy, so an empty `?password=` collapses to `None` and was
already rejected. The genuinely reachable vector is an empty **`session` cookie**
(`Cookie: session=`), which survives as `""` (the chain's last operand) and
reached `_valid`. The WebSocket path, `_valid(password or session)`, was
exploitable the same way. Both were confirmed live before the fix and are now
covered by parametrized tests. Severity and remedy unchanged; only the vector
name was wrong. The error came from testing `_valid()` in isolation rather than
through its callers — isolation proved the flaw existed, not that it was
reachable.

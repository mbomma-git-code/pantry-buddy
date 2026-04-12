# Agent Plan Wrapup + Push to Prod

## Description
Use when the user wants to close out a Cursor plan (mark tasks done, save plan under `.cursor/plans`) **and** push to production with the full local test matrix, a defined commit workflow, and post-push deployment verification.

## Preconditions
- Default branch for production deploy: **main** (matches `.github/workflows/deploy-infrastructure.yml`).
- Deployment runs on GitHub Actions after push when changed paths include `infrastructure/**`, `backend/**`, `frontend/**`, `data/recipes_json/**`, or the workflow file itself.

## Instructions

### A. Plan wrap-up (stop if incomplete)
1. Verify all tasks in the active plan are completed. If any are incomplete, list them and **stop**; do not run tests or push.
2. If complete: mark all plan tasks done, set `isProject: true` if applicable, and save the plan under `.cursor/plans/` per project conventions.

### B. Local unit tests (entire project)
Run from repository root unless noted.

1. **Frontend**
   - `cd frontend && npm test`
2. **Python**
   - Prefer: `python3 -m pytest tests/`  
   - If pytest is unavailable: `python3 -m unittest discover -s tests -p 'test_*.py'`

Do not proceed if any command fails.

### C. End-to-end integration tests (full-project local smoke)
One-time setup if needed: `make setup-local-browser-tests`

Then run the browser smoke test (starts local adapter + frontend if not running):
- `make qa-local-frontend`

(Optional variants documented in `tests/LOCAL_QA.md`: reuse servers, headed mode.)

Do not proceed if this fails.

### D. Commit method (must follow exactly)
Document here the team’s rule; example:

- **Branch:** work on `feature/...` or direct on `main` (pick one).
- **Staging:** `git status` → `git add` only intentional paths.
- **Commit message:** single line, imperative, e.g. `feat: describe change` or project convention.
- **History:** single commit per push **or** squash before merge (specify).
- **Push:** `git push origin <branch>`; for production, merge to **`main`** (PR or fast-forward as per team policy).

The agent must not push secrets; no credentials in commit messages.

### E. Push to mainline
After tests pass and commit is created:
1. Ensure the branch that triggers deploy contains the commit (typically **`main`** after merge).
2. Push: `git push origin main` (or merge PR and let GitHub merge to `main`).

### F. Verify deployment succeeded
After the push lands on `main`:

1. **GitHub Actions:** Confirm the workflow **“Deploy Infrastructure (CDK)”** run for that commit completed successfully (green). If using GitHub CLI: `gh run list --workflow=deploy-infrastructure.yml --limit 5` then `gh run watch <run-id>`.
2. **If the workflow did not run:** Check whether the commit only touched paths **outside** the workflow’s `paths:` filters; if so, either adjust what you ship or run deploy manually per team process.
3. **Optional prod smoke (recommended):** Follow the post-deploy checklist in project docs (e.g. open live site, generate meal plan, confirm recipe source links) — see `docs/HIGH_LEVEL_DESIGN_v2.md` / `tests/LOCAL_QA.md` for alignment.

Report success only when (1) is green and, if required by the user, (3) is done.

## Notes
- Local E2E exercises **local** servers; production verification is **post-push** (CI + optional live smoke).
- Infrastructure has no `npm test` in `infrastructure/package.json`; CDK validation is primarily `cdk synth` / deploy in CI.
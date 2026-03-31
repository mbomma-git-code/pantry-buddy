# Local QA

Use the local browser smoke test to verify the full frontend flow against the local adapter and canonical recipe artifact.

## One-time setup

From the repo root:

```bash
make setup-local-browser-tests
```

The smoke test uses the project-local `.venv` and will prefer an already installed local browser such as Google Chrome.

Each run writes observability artifacts under `test-results/local-e2e/<timestamp>/` by default:

- `trace.zip` for Playwright trace replay
- `videos/` for browser video capture
- `screenshots/` for step-by-step snapshots

## Fast path

If you want the test runner to start its own frontend server and local adapter:

```bash
make qa-local-frontend
```

This will:

- start the static frontend if it is not already running
- start `backend/local_adapter.py` with local canonical recipe data if it is not already running
- open the frontend in a real browser via Playwright
- click `Generate Meal Plan`
- verify the recipe panel shows source attribution and a working source link
- click a second recipe card and verify the panel updates
- capture a Playwright trace zip, browser video, and step screenshots

## Watch the clicks live

To run the same flow in a visible browser with slower actions:

```bash
make qa-local-frontend-headed SLOW_MO_MS=1500 HOLD_OPEN_SECONDS=5
```

## Reuse running local servers

If you already have local servers running, point the smoke test at them directly:

```bash
make qa-local-frontend-reuse FRONTEND_URL="http://127.0.0.1:8080/" API_BASE_URL="http://127.0.0.1:8002"
```

You can also combine reuse mode with custom artifacts or slower motion by calling the script directly:

```bash
.venv/bin/python tools/run_local_frontend_e2e.py \
  --frontend-url "http://127.0.0.1:8080/" \
  --api-base-url "http://127.0.0.1:8002" \
  --reuse-existing-only \
  --headed \
  --slow-mo-ms 1500 \
  --hold-open-seconds 5 \
  --artifacts-dir "test-results/local-e2e/manual-observe"
```

## Expected result

The command prints JSON similar to:

```json
{
  "frontendUrl": "http://127.0.0.1:8080/?apiBaseUrl=http%3A%2F%2F127.0.0.1%3A8002",
  "firstTitle": "Toasted Coconut Baked Oatmeal",
  "firstSource": "Minimalist Baker",
  "firstLink": "https://minimalistbaker.com/toasted-coconut-baked-oatmeal/",
  "secondTitle": "Kale Salad - Love and Lemons",
  "secondSource": "Love and Lemons",
  "secondLink": "https://www.loveandlemons.com/kale-salad/",
  "artifactsDir": "/Users/.../test-results/local-e2e/20260331-120000",
  "traceZip": "/Users/.../test-results/local-e2e/20260331-120000/trace.zip",
  "videoPath": "/Users/.../test-results/local-e2e/20260331-120000/videos/<id>.webm",
  "screenshots": [
    "/Users/.../test-results/local-e2e/20260331-120000/screenshots/01_loaded_frontend.png",
    "/Users/.../test-results/local-e2e/20260331-120000/screenshots/02_generated_meal_plan.png",
    "/Users/.../test-results/local-e2e/20260331-120000/screenshots/03_first_selected_recipe.png",
    "/Users/.../test-results/local-e2e/20260331-120000/screenshots/04_second_selected_recipe.png"
  ]
}
```

## Review the trace

Open the captured Playwright trace with:

```bash
.venv/bin/python -m playwright show-trace test-results/local-e2e/<timestamp>/trace.zip
```

## Troubleshooting

- If `.venv/bin/python` does not exist, rerun `make setup-local-browser-tests`.
- If Playwright cannot launch a browser, make sure a local browser such as Google Chrome is installed.
- If you want to use the Playwright-managed browser instead of a local browser, run:

```bash
.venv/bin/python -m playwright install chromium
```

- If the smoke test fails with a connection error, confirm the frontend URL and API base URL are reachable.

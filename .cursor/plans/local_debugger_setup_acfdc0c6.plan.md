---
name: local debugger setup
overview: Set up a local Cursor/VS Code debugging workflow that lets you click through the frontend and step into the Python Lambda code, while keeping the initial scope small enough to work with the repo’s current static frontend and Lambda-only backend structure.
todos:
  - id: add-local-adapter
    content: Create a small local Python HTTP adapter that converts browser requests into API Gateway-style Lambda events.
    status: completed
  - id: enable-local-data
    content: Let the backend read recipe JSON from local files during debug runs instead of always using S3.
    status: completed
  - id: wire-frontend-local
    content: Add a safe local frontend API override for debug sessions.
    status: completed
  - id: add-launch-configs
    content: Create Cursor/VS Code launch and task configs for browser plus Python debugging.
    status: completed
  - id: expose-v2-locally
    content: Route local `/v2/generate-meal-plan` requests into the existing `handle_v2()` path for inspection.
    status: completed
  - id: todo-1772941767412-yl06u91ix
    content: Press one debug configuration in Cursor and open the frontend locally.
    status: completed
  - id: todo-1772942071590-7wv4bwf02
    content: Run the debugger flow and verify breakpoints hit in frontend/app.js, backend/local_adapter.py, and backend/lambda_function.py
    status: pending
isProject: false
---

# Plan To Set Up Local Debugging For The API Flow

## Goal

Create a local, breakpoint-friendly workflow so you can start in the browser UI, trigger the meal-plan request, and step into the Python backend code from Cursor. Since this repo has a static frontend and an AWS Lambda handler rather than a local web server, the setup needs a thin local adapter layer.

## Proposed approach

1. Add a small local HTTP adapter for the Lambda.

Create a local Python server near [backend/lambda_function.py](/Users/mounitha/Desktop/PantryBuddy/backend/lambda_function.py) that accepts browser `POST` requests, builds an API Gateway-style event, calls `lambda_handler(...)`, and translates the Lambda proxy response back into normal HTTP. This is the simplest way to make the browser request path debuggable without introducing SAM, Docker, or a full web framework.

1. Add a local-data mode so the backend can run without AWS.

Refactor recipe loading in [backend/lambda_function.py](/Users/mounitha/Desktop/PantryBuddy/backend/lambda_function.py) to support local files from [data/recipes_json](/Users/mounitha/Desktop/PantryBuddy/data/recipes_json) during debugging instead of always calling S3. Without this, local breakpoints would still depend on live AWS credentials and S3 availability.

1. Point the frontend at the local adapter during debug sessions.

Update [frontend/config.js](/Users/mounitha/Desktop/PantryBuddy/frontend/config.js) or add a local override so the browser uses `http://127.0.0.1:<port>` instead of the deployed API URL when debugging. Keep the production API URL path intact outside debug mode so local tooling does not interfere with deployed behavior.

1. Add Cursor/VS Code launch configurations.

Create `.vscode` debug configuration files so one command can:

- start a static file server for [frontend/index.html](/Users/mounitha/Desktop/PantryBuddy/frontend/index.html)
- launch the Python local adapter under the debugger
- open the browser against the local frontend
- optionally provide a direct backend-only launch that invokes the Lambda with a sample event

1. Include the `v2` route in the local adapter so you can trace that code path.

The local adapter should expose both `/generate-meal-plan` and `/v2/generate-meal-plan`, using the endpoint map from [backend/config.py](/Users/mounitha/Desktop/PantryBuddy/backend/config.py). That will let you step into `handle_v2()` in [backend/lambda_function.py](/Users/mounitha/Desktop/PantryBuddy/backend/lambda_function.py), even though the current implementation will stop at undefined helpers.

1. Keep the initial debugger scope intentionally minimal.

Avoid adding SAM, LocalStack, or deployment-integrated debugging for the first pass. The repo currently has no local backend runtime, no test harness, and no existing debugger config, so a thin adapter plus launch configs is the fastest path to useful breakpoints.

## Important limitation

`v2` is not fully implemented today. The handler in [backend/lambda_function.py](/Users/mounitha/Desktop/PantryBuddy/backend/lambda_function.py) calls undefined functions, and the deployed API in [infrastructure/lib/pantrybuddy-stack.ts](/Users/mounitha/Desktop/PantryBuddy/infrastructure/lib/pantrybuddy-stack.ts) does not provision `/v2/generate-meal-plan`. This debugger setup will let you trace the flow into `v2`, but the request will still fail once execution reaches those missing pieces.

## Files likely to change

- [backend/lambda_function.py](/Users/mounitha/Desktop/PantryBuddy/backend/lambda_function.py)
- [backend/config.py](/Users/mounitha/Desktop/PantryBuddy/backend/config.py)
- [frontend/config.js](/Users/mounitha/Desktop/PantryBuddy/frontend/config.js)
- New `.vscode/launch.json`
- New `.vscode/tasks.json`
- New local adapter file under `backend/`
- Optional sample event file under `events/`

## Success criteria

- You can press one debug configuration in Cursor and open the frontend locally.
- Clicking the button in the browser pauses in frontend code, then steps into the Python backend adapter and `lambda_handler(...)`.
- Local debugging works without requiring S3 reads.
- The local adapter can hit `/v2/generate-meal-plan` and reach `handle_v2()` so you can inspect the current flow and failure point.


# Cursor Debug Session: V2 Endpoint Routing Incident

## Context
- **Date:** 2026-03-09
- **Frontend URL:** `http://pantrybuddystack-websitebucket75c24d94-3wb9nazcn002.s3-website.us-east-2.amazonaws.com/`
- **API base URL:** `https://bkq2ftn73g.execute-api.us-east-2.amazonaws.com/prod`
- **Primary symptom:** UI showed **"Failed to generate meal plan"**

## Problem Statement
After switching to V2, the frontend intermittently continued calling the V1 route and failed with a generic UI alert.

## Hypotheses Investigated
1. V2 API endpoint was broken.
2. Frontend config did not deploy correctly.
3. Browser was still using stale cached JS/config and calling V1.
4. Frontend error handling masked the underlying HTTP error.

## Runtime Evidence Collected
- Direct runtime calls showed:
  - `POST /prod/v2/generate-meal-plan` -> `200` with valid `week` payload.
  - `POST /prod/generate-meal-plan` -> `500 Internal Server Error`.
- Live deployed assets were inspected:
  - `config.js` had `API_VERSION: 'v2'`.
  - `index.html` loaded versioned scripts.
- Browser validation by user:
  - Initially observed `CONFIG.API_VERSION` as `v1` and route resolving to V1 path.
  - Later verified request URL used V2 and returned `200` with successful table render.

## Root Cause
Client-side stale cache served older frontend assets in some browser sessions, causing calls to the legacy V1 route (`/generate-meal-plan`) which was no longer healthy for this flow.

## Fixes Applied
1. Switched stack/frontend defaults to V2 endpoint routing.
2. Updated API Gateway route to `/v2/generate-meal-plan`.
3. Added cache-busting query version for script assets in `frontend/index.html`:
   - `config.js?v=20260309v2`
   - `app.js?v=20260309v2`
4. Hardened frontend call path to explicitly use V2 endpoint construction.
5. Removed temporary debug instrumentation after post-fix verification.

## Verification Outcome
- Final runtime verification confirmed:
  - Network POST request URL ended with `/prod/v2/generate-meal-plan`
  - Status code was `200`
  - Meal plan table rendered successfully in UI

## Relevant Commits (Session)
- `b00169d` - Switch PantryBuddy to v2 API route
- `123e510` - Add temporary frontend runtime debug instrumentation
- `6de541c` - Bust frontend script cache for v2 route config
- `3e3d288` - Force frontend meal-plan calls to v2 route
- `e60e016` - Remove temporary frontend debug instrumentation

## Follow-up Recommendations
- Keep script cache-busting in place for static S3 website deployments.
- Consider build-time hashed asset filenames for stronger cache invalidation.
- Optionally improve frontend error handling to show HTTP status/details for faster future diagnosis.

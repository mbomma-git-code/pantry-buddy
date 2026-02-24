# PantryBuddy AWS Infrastructure (CDK)

This folder defines the AWS infrastructure for PantryBuddy using **AWS CDK** (TypeScript).

## What gets created

| Resource | Purpose |
|----------|---------|
| **WebsiteBucket** | S3 bucket with static website hosting for the frontend (index.html, app.js, config.js). |
| **DataBucket** | S3 bucket holding recipe JSON files; private, only Lambda has read access. |
| **MealPlanFunction** | Lambda (Python 3.11) that reads recipes from DataBucket and returns a weekly meal plan. |
| **MealPlanApi** | API Gateway REST API with `POST /generate-meal-plan` and CORS. |
| **DeployRecipeData** | Copies `data/recipes_json/*.json` into DataBucket under `recipes_json/`. |
| **DeployFrontend** | Copies `frontend/*` into WebsiteBucket on each deploy. |

You can replace the manual S3 bucket you used for static hosting with the **WebsiteBucket** created by this stack (see “Using your existing bucket” below if you prefer to keep the current bucket).

## Prerequisites

- **Node.js** 18+
- **AWS CLI** configured (`aws configure` or env vars)
- **AWS CDK** bootstrapped in your account/region:
  ```bash
  npx cdk bootstrap
  ```

## Commands

From the `infrastructure/` directory:

```bash
# Install dependencies
npm install

# Synthesize CloudFormation template (no deploy)
npm run synth

# Show diff vs deployed stack
npm run diff

# Deploy the stack (creates/updates resources)
npm run deploy

# Destroy the stack
npm run destroy
```

First-time deploy will create the two S3 buckets, Lambda, API Gateway, and deploy recipe data + frontend. After deploy, use the **ApiEndpoint** and **WebsiteURL** outputs.

## After first deploy

1. **Update frontend API URL**  
   Set `frontend/config.js` → `API_BASE_URL` to the **ApiEndpoint** value (e.g. `https://xxxx.execute-api.us-east-2.amazonaws.com/prod/`).  
   Then redeploy the frontend (either run `cdk deploy` again or your existing CI that syncs to S3).

2. **Optional: Keep using your existing static hosting bucket**  
   - Either point your GitHub Actions (or other CI) to the new **WebsiteBucket** name and stop using the manual bucket, or  
   - Import your existing bucket into the stack (e.g. via `Bucket.fromBucketName`) and remove the `WebsiteBucket` construct and `DeployFrontend` if you want CDK to only manage Lambda, API Gateway, and the data bucket.

## Region

Default region is `us-east-2` (set in `bin/infrastructure.ts`). Override with:

```bash
CDK_DEFAULT_REGION=us-east-1 npm run deploy
```

Or set `AWS_REGION` / `CDK_DEFAULT_REGION` in your environment.

## Outputs

After `cdk deploy`, the stack exports:

- **WebsiteBucketName** – S3 bucket for the static site  
- **WebsiteURL** – Website URL of the bucket  
- **DataBucketName** – S3 bucket for recipe JSON  
- **ApiEndpoint** – Base URL of the API (e.g. `https://.../prod/`)  
- **GenerateMealPlanUrl** – Full URL for `POST /generate-meal-plan`

Use these to configure the frontend and any CI/CD (e.g. GitHub Actions) to use the new buckets and API.

## GitHub Actions (CDK deploy)

A separate workflow deploys the CDK stack when relevant paths change on `main`, or when run manually.

- **Workflow:** `.github/workflows/deploy-infrastructure.yml`
- **Triggers:** Push to `main` that touches `infrastructure/`, `backend/`, or `data/recipes_json/`; or **Actions → Deploy Infrastructure (CDK) → Run workflow**.

**Required setup:**

1. **Repository variables** (Settings → Secrets and variables → Actions → Variables):
   - `AWS_CDK_DEPLOY_ROLE_ARN` – IAM role ARN for CDK (e.g. `arn:aws:iam::ACCOUNT_ID:role/GitHubCDKDeployRole`).
   - `AWS_ACCOUNT_ID` – Your AWS account ID.

2. **IAM role:** The role must trust GitHub’s OIDC provider and have permissions for CDK/CloudFormation (e.g. CloudFormation, IAM, S3, Lambda, API Gateway). Use the same OIDC trust pattern as your existing `GitHubS3DeployRole`, with a policy that allows CDK deployment.

3. **Optional:** Run `npm install` in `infrastructure/` and commit `package-lock.json` so the workflow can use `npm ci` for faster, reproducible installs.

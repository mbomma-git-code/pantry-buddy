# PantryBuddy AWS Infrastructure (CDK)

This folder defines the AWS infrastructure for PantryBuddy using **AWS CDK** (TypeScript).

## What gets created

| Resource | Purpose |
|----------|---------|
| **WebsiteBucket** | S3 bucket with static website hosting for the frontend (`frontend/src`: index.html, app.js, config.js). |
| **DataBucket** | S3 bucket holding recipe JSON and `kb/structured/` corpus; private. |
| **MealPlanFunction** | Lambda (Python 3.11) that reads recipes from DataBucket and returns a weekly meal plan. |
| **MealPlanApi** | API Gateway REST API with `POST /v2/generate-meal-plan`, `/v3/chat`, `/v3/suggest-meals`, and CORS. |
| **DeployRecipeData** | Copies `data/recipes_json/*.json` into DataBucket under `recipes_json/`. |
| **DeployKbStructured** | Copies `data/kb/structured/` into DataBucket under `kb/structured/` (`prune: false`). |
| **RecipeKnowledgeBase** | Bedrock Knowledge Base + OpenSearch Serverless vector collection/index + Titan Embeddings V2 + S3 data source on `kb/structured/`. |
| **KbSyncRole** | IAM role for uploading corpus objects and starting ingestion jobs. |
| **DeployFrontend** | Copies `frontend/src/*` into WebsiteBucket on each deploy. |

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
   Set `frontend/src/config.js` → `API_BASE_URL` to the **ApiEndpoint** value (e.g. `https://xxxx.execute-api.us-east-2.amazonaws.com/prod/`).  
   Then redeploy the frontend (either run `cdk deploy` again or your existing CI that syncs to S3).

2. **Enable Bedrock model access**  
   In the Bedrock console (us-east-2), enable **Amazon Titan Text Embeddings V2** (`amazon.titan-embed-text-v2:0`) and **Claude 3.5 Haiku** (`anthropic.claude-3-5-haiku-20241022-v1:0`). Titan is required for KB ingestion; Haiku is the default v3 chat generator.

3. **Build and ingest the structured corpus**  
   ```bash
   make sync-kb-index \
     DATA_BUCKET=<DataBucketName> \
     KNOWLEDGE_BASE_ID=<KnowledgeBaseId> \
     DATA_SOURCE_ID=<KnowledgeBaseDataSourceId>
   ```
   Or assume **KbSyncRoleArn** and run `tools/sync_kb_index.py`. Full re-upload: add `--full` via the script.

4. **Optional: Keep using your existing static hosting bucket**  
   - Either point your GitHub Actions (or other CI) to the new **WebsiteBucket** name and stop using the manual bucket, or  
   - Import your existing bucket into the stack (e.g. via `Bucket.fromBucketName`) and remove the `WebsiteBucket` construct and `DeployFrontend` if you want CDK to only manage Lambda, API Gateway, and the data bucket.

## Local development (v3 RAG)

Production Lambda always receives `KNOWLEDGE_BASE_ID` from the stack and calls `bedrock:Retrieve` then `bedrock:InvokeModel`.

For local adapter / unit tests:

| Goal | Env |
|------|-----|
| Read recipes from disk | `RECIPE_DATA_SOURCE=local` |
| Lexical retrieval (no AWS) | leave `KNOWLEDGE_BASE_ID` unset/empty |
| Deterministic answers (no LLM) | `RAG_GENERATOR=extract` or `fake` |
| Hit the deployed KB | set `KNOWLEDGE_BASE_ID` (+ AWS creds); optional `GENERATOR_MODEL_ID` |

Indexing stays offline (`make build-kb-index` / `make sync-kb-index`). Each chat request pays for query embedding (inside Retrieve) + one generator InvokeModel call.

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
- **DataBucketName** – S3 bucket for recipe JSON and `kb/structured/`  
- **ApiEndpoint** – Base URL of the API (e.g. `https://.../prod/`)  
- **GenerateMealPlanUrl** – Full URL for `POST /v2/generate-meal-plan`  
- **V3ChatUrl** / **V3SuggestMealsUrl** – v3 routes  
- **KnowledgeBaseId** / **KnowledgeBaseDataSourceId** – Bedrock KB IDs (Lambda gets `KNOWLEDGE_BASE_ID` automatically)
- **GeneratorModelId** – Claude model wired as `GENERATOR_MODEL_ID`
- **KbSyncRoleArn** – Role for corpus upload + ingestion  
- **EmbeddingModelId** – `amazon.titan-embed-text-v2:0` (also set on Lambda as `EMBEDDING_MODEL_ID`)

Use these to configure the frontend and any CI/CD (e.g. GitHub Actions) to use the new buckets and API.

## GitHub Actions (CDK deploy)

A separate workflow deploys the CDK stack when relevant paths change on `main`, or when run manually.

- **Workflow:** `.github/workflows/deploy-infrastructure.yml`
- **Triggers:** Push to `main` that touches `infrastructure/`, `backend/`, or `data/recipes_json/`; or **Actions → Deploy Infrastructure (CDK) → Run workflow**.

**Required setup:**

1. **Repository variables** (Settings → Secrets and variables → Actions → Variables):
   - `AWS_CDK_DEPLOY_ROLE_ARN` – IAM role ARN for CDK (e.g. `arn:aws:iam::ACCOUNT_ID:role/GitHubCDKDeployRole`).
   - `AWS_ACCOUNT_ID` – Your AWS account ID.

2. **IAM role:** The role must trust GitHub’s OIDC provider and include **SSM** (e.g. `ssm:GetParameter` on `parameter/cdk-bootstrap/*`) plus CloudFormation, S3, IAM, Lambda, API Gateway, and Logs. If you see `AccessDeniedException` on `ssm:GetParameter`, add the policy in [IAM_CDK_DEPLOY.md](IAM_CDK_DEPLOY.md) to the role set in `AWS_CDK_DEPLOY_ROLE_ARN`.

3. **Optional:** Run `npm install` in `infrastructure/` and commit `package-lock.json` so the workflow can use `npm ci` for faster, reproducible installs.

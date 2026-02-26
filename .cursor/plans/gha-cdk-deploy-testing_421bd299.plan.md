---
name: gha-cdk-deploy-testing
overview: Use GitHub Actions as the cloud runner to build and deploy the PantryBuddy CDK stack, and verify deployments end-to-end without relying on local disk space.
todos:
  - id: iam-role-gha
    content: Create and configure an IAM role (GitHubCDKDeployRole) for GitHub Actions OIDC with permissions for CDK/CloudFormation and related services
    status: completed
  - id: gha-repo-vars
    content: Add AWS_CDK_DEPLOY_ROLE_ARN and AWS_ACCOUNT_ID variables in GitHub repo settings for Actions
    status: completed
  - id: verify-deploy-workflow
    content: Review and, if needed, adjust .github/workflows/deploy-infrastructure.yml for correct region, triggers, and commands
    status: completed
  - id: run-first-cdk-deploy
    content: Trigger the Deploy Infrastructure (CDK) workflow and confirm CDK bootstrap and deploy succeed in GitHub Actions logs
    status: completed
  - id: check-aws-resources
    content: Verify CloudFormation stack, S3 buckets, Lambda, and API Gateway resources created by the CDK deploy
    status: completed
  - id: wire-app-to-infra
    content: Point frontend config and backend S3 bucket config to the CDK-created resources and redeploy the UI
    status: pending
  - id: e2e-verify
    content: Perform end-to-end tests (API + frontend) after a GitHub Actions-driven deploy and adjust IAM/policies as needed
    status: pending
isProject: false
---

# Test CDK Deployments via GitHub Actions

## 1. Confirm repo and CDK layout

- **CDK app entry**: `[infrastructure/bin/infrastructure.ts](infrastructure/bin/infrastructure.ts)` defines `PantryBuddyStack` with env from `CDK_DEFAULT_ACCOUNT` / `CDK_DEFAULT_REGION`.
- **Infra project**: `[infrastructure/package.json](infrastructure/package.json)` contains CDK scripts (`deploy`, `synth`, etc.) and dependencies (`aws-cdk-lib`, `aws-cdk`).
- **GHA workflow**: `[.github/workflows/deploy-infrastructure.yml](.github/workflows/deploy-infrastructure.yml)` already checks out the repo, installs infra deps, configures AWS, runs `cdk bootstrap` and `cdk deploy`.

## 2. Configure AWS IAM role for GitHub Actions

- **Goal**: Allow GitHub Actions runners to assume an IAM role in your AWS account via OIDC and perform CDK deployments.
- **Steps (one-time in AWS console)**:
  - Create an IAM role (e.g. `GitHubCDKDeployRole`) with **trusted entity = Web identity** using `token.actions.githubusercontent.com` as the provider.
  - Restrict the trust policy to your repo (e.g. `repo:OWNER/REPO:*`) and audience `sts.amazonaws.com`.
  - Attach a policy that grants necessary permissions for CloudFormation, S3, Lambda, API Gateway, IAM, and CloudWatch Logs used by `PantryBuddyStack`.
  - Copy the role ARN for use in GitHub.

## 3. Add GitHub repository variables

- In your GitHub repo: **Settings → Secrets and variables → Actions → Variables**:
  - Add `AWS_CDK_DEPLOY_ROLE_ARN` with the IAM role ARN you created.
  - Add `AWS_ACCOUNT_ID` with your AWS account ID (e.g. `613926939057`).
- These map directly to the values referenced in `[.github/workflows/deploy-infrastructure.yml](.github/workflows/deploy-infrastructure.yml)` for `role-to-assume` and `CDK_DEFAULT_ACCOUNT`.

## 4. Validate and tune the deploy-infrastructure workflow

- **Review** `[.github/workflows/deploy-infrastructure.yml](.github/workflows/deploy-infrastructure.yml)`:
  - Confirm `AWS_REGION` matches your desired region (currently `us-east-2`).
  - Ensure `paths` under `on.push` include the folders you care about for infra changes (`infrastructure/`, `backend/`, `data/recipes_json/`).
  - Confirm install step uses `npm ci` when `package-lock.json` exists, else `npm install`, in `infrastructure/`.
  - Confirm `cdk bootstrap` and `cdk deploy --require-approval never --all` run from the `infrastructure/` working directory.
- **Optional hardening**:
  - If you prefer to **only** deploy on manual trigger at first, change or add a workflow that uses `workflow_dispatch` without `on.push`.

## 5. First end-to-end CDK deploy via GitHub Actions

- In GitHub, go to **Actions → Deploy Infrastructure (CDK)**.
- Click **Run workflow** (workflow_dispatch) and choose the branch to deploy (typically `main`).
- Monitor the job steps:
  - `Checkout code` completes successfully.
  - `Setup Node.js` and `Install dependencies` finish without errors.
  - `Configure AWS credentials` shows a successful role assumption.
  - `CDK bootstrap` runs (on first deploy) and either succeeds or is skipped on subsequent runs.
  - `CDK deploy` completes with `PantryBuddyStack` in `CREATE_COMPLETE`/`UPDATE_COMPLETE` state.

## 6. Verify resources in AWS

- In the AWS console:
  - **CloudFormation**: Confirm a stack named `PantryBuddyStack` exists in your target region with status `CREATE_COMPLETE` or `UPDATE_COMPLETE`.
  - **S3**: Check that the website and data buckets defined in `[infrastructure/lib/pantrybuddy-stack.ts](infrastructure/lib/pantrybuddy-stack.ts)` exist.
  - **Lambda**: Ensure the meal-plan Lambda function is created and has environment variables for S3 bucket and region.
  - **API Gateway**: Confirm the REST API is present, with a `POST /generate-meal-plan` method.
- Note the stack **Outputs** for `WebsiteBucketName`, `WebsiteURL`, `DataBucketName`, `ApiEndpoint`, and `GenerateMealPlanUrl`.

## 7. Connect frontend/backend to the deployed infra

- **Frontend**: In `[frontend/config.js](frontend/config.js)`, set `API_BASE_URL` to the **ApiEndpoint** output (e.g. `https://xxxx.execute-api.us-east-2.amazonaws.com/prod`).
- **Backend**: In `[backend/config.py](backend/config.py)`, ensure `AWS_CONFIG['BUCKET_NAME']` matches the data bucket created by the CDK stack (or that the stack is configured to use your existing bucket name).
- Use your existing UI deploy workflow `[.github/workflows/deploy-ui.yml](.github/workflows/deploy-ui.yml)` (or a manual `aws s3 sync`) to update the static site in S3 with the correct frontend config.

## 8. Functional testing after a GitHub Actions deploy

- **Test API directly**:
  - Use `curl` or Postman to send a `POST {}` to the `GenerateMealPlanUrl` (from stack outputs).
  - Expect a `200` response with a JSON body containing a `week` array of meal plans.
- **Test via frontend**:
  - Visit the static website URL (either existing bucket URL or `WebsiteURL` output from the stack).
  - Click the **Generate Meal Plan** button and verify the table populates with 7 days and 4 meals per day.
- **Check logs**:
  - In CloudWatch Logs for the Lambda function, confirm invocations are logged and there are no unexpected errors.

## 9. Ongoing usage and safety

- **Normal workflow**:
  - Develop in Cursor locally, commit/push changes.
  - Trigger **Deploy Infrastructure (CDK)** via Actions (either on push to `main` or manually, depending on workflow config).
  - Verify CloudFormation and app behavior after each deploy.
- **Safety options**:
  - Keep `--require-approval never` while iterating; later, consider removing it and using `cdk deploy` with approval prompts for manual/CLI runs.
  - Optionally add branch protections and pull-request reviews for `main` so only reviewed changes can reach the branch that Actions deploys.

## 10. Troubleshooting common issues

- **Role assumption failures**: Check `AWS_CDK_DEPLOY_ROLE_ARN` value and the IAM role trust policy conditions (repo name, audience).
- **Permission errors**: Expand the IAM policy on the CDK role to include missing services/actions (CloudFormation, S3, Lambda, API Gateway, IAM, Logs).
- **Region mismatches**: Ensure `AWS_REGION` in the workflow, `CDK_DEFAULT_REGION`, and the CloudFormation console view all point to the same region.
- **Dependency install failures**: If `npm ci` fails due to missing `package-lock.json`, generate and commit `infrastructure/package-lock.json` once (or rely on the `npm install` fallback in the workflow).


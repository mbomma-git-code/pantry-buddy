# IAM permissions for CDK deploy (GitHub Actions)

The Deploy Infrastructure workflow assumes the role set in `AWS_CDK_DEPLOY_ROLE_ARN`.  
If that role is **GitHubS3DeployRole** (or any role that only had S3 permissions), CDK deploy will fail with:

```text
AccessDeniedException: User: arn:aws:sts::ACCOUNT:assumed-role/GitHubS3DeployRole/GitHubActions
is not authorized to perform: ssm:GetParameter on resource:
arn:aws:ssm:REGION:ACCOUNT:parameter/cdk-bootstrap/hnb659fds/version
because no identity-based policy allows the ssm:GetParameter action
```

CDK needs to read the bootstrap version from SSM before deploying. The role must also be allowed to create/update CloudFormation stacks, S3 buckets, Lambda, API Gateway, IAM roles, and related resources. For **first-time bootstrap**, the role needs `ssm:PutParameter` so CDK can create the bootstrap version parameter.

## Fix: add this policy to the role used by the workflow

Attach an **inline policy** (or a dedicated managed policy) to the role referenced by `AWS_CDK_DEPLOY_ROLE_ARN` (e.g. **GitHubS3DeployRole** or **GitHubCDKDeployRole**) with at least these permissions. Replace `ACCOUNT_ID` and `REGION` (e.g. `613926939057` and `us-east-2`) if you use a different account/region.

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "CDKBootstrapSSM",
      "Effect": "Allow",
      "Action": [
        "ssm:GetParameter",
        "ssm:PutParameter",
        "ssm:DeleteParameter"
      ],
      "Resource": "arn:aws:ssm:REGION:ACCOUNT_ID:parameter/cdk-bootstrap/*"
    },
    {
      "Sid": "CDKDeploy",
      "Effect": "Allow",
      "Action": [
        "cloudformation:*",
        "s3:*",
        "lambda:*",
        "apigateway:*",
        "logs:*",
        "sts:GetCallerIdentity"
      ],
      "Resource": "*"
    },
    {
      "Sid": "IAMForLambdaExecutionRole",
      "Effect": "Allow",
      "Action": [
        "iam:CreateRole",
        "iam:DeleteRole",
        "iam:GetRole",
        "iam:PassRole",
        "iam:AttachRolePolicy",
        "iam:DetachRolePolicy",
        "iam:PutRolePolicy",
        "iam:DeleteRolePolicy",
        "iam:GetRolePolicy",
        "iam:ListAttachedRolePolicies",
        "iam:ListRolePolicies",
        "iam:TagRole",
        "iam:UntagRole"
      ],
      "Resource": "*"
    }
  ]
}
```

### Steps in AWS Console

1. IAM → **Roles** → select the role (e.g. **GitHubS3DeployRole**).
2. **Add permissions** → **Create inline policy** → **JSON** tab.
3. Paste the policy above (with your `ACCOUNT_ID` and `REGION`).
4. Name the policy (e.g. `CDKDeployPolicy`) and save.

After saving, re-run the **Deploy Infrastructure (CDK)** workflow. The bootstrap step can create the SSM parameter; the deploy step will then pass.

### Optional: use a dedicated CDK role

To keep S3 deploy and CDK deploy separate, create a new role (e.g. **GitHubCDKDeployRole**) with the same GitHub OIDC trust as your S3 role, attach the policy above, and set the repo variable `AWS_CDK_DEPLOY_ROLE_ARN` to that role’s ARN.

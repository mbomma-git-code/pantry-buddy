import * as path from 'path';
import * as cdk from 'aws-cdk-lib';
import * as iam from 'aws-cdk-lib/aws-iam';
import * as s3 from 'aws-cdk-lib/aws-s3';
import * as s3deploy from 'aws-cdk-lib/aws-s3-deployment';
import * as lambda from 'aws-cdk-lib/aws-lambda';
import * as apigateway from 'aws-cdk-lib/aws-apigateway';
import { Construct } from 'constructs';
import {
  RecipeKnowledgeBase,
  TITAN_EMBED_TEXT_V2_MODEL_ID,
} from './knowledge-base';

/** Claude 3.5 Haiku — default v3 chat generator (cost/latency). */
export const CLAUDE_3_5_HAIKU_MODEL_ID = 'anthropic.claude-3-5-haiku-20241022-v1:0';

export class PantryBuddyStack extends cdk.Stack {
  constructor(scope: Construct, id: string, props?: cdk.StackProps) {
    super(scope, id, props);

    const backendPath = path.join(__dirname, '../../backend');
    const recipeDataPath = path.join(__dirname, '../../data/recipes_json');
    const kbStructuredPath = path.join(__dirname, '../../data/kb/structured');
    const frontendPath = path.join(__dirname, '../../frontend/src');

    // --- S3: Static website bucket (frontend) ---
    const websiteBucket = new s3.Bucket(this, 'WebsiteBucket', {
      bucketName: undefined, // let CDK generate a unique name
      blockPublicAccess: new s3.BlockPublicAccess({
        blockPublicAcls: false,
        blockPublicPolicy: false,
        ignorePublicAcls: false,
        restrictPublicBuckets: false,
      }),
      websiteIndexDocument: 'index.html',
      websiteErrorDocument: 'index.html',
      removalPolicy: cdk.RemovalPolicy.DESTROY,
      autoDeleteObjects: true,
    });
    websiteBucket.addToResourcePolicy(
      new cdk.aws_iam.PolicyStatement({
        sid: 'PublicReadGetObject',
        effect: cdk.aws_iam.Effect.ALLOW,
        principals: [new cdk.aws_iam.AnyPrincipal()],
        actions: ['s3:GetObject'],
        resources: [websiteBucket.arnForObjects('*')],
      })
    );

    // --- S3: Recipe data bucket (Lambda reads from here; KB reads kb/structured/) ---
    const dataBucket = new s3.Bucket(this, 'DataBucket', {
      bucketName: undefined,
      blockPublicAccess: s3.BlockPublicAccess.BLOCK_ALL,
      removalPolicy: cdk.RemovalPolicy.DESTROY,
      autoDeleteObjects: true,
    });

    // Deploy recipe JSON files into the data bucket under recipes_json/
    new s3deploy.BucketDeployment(this, 'DeployRecipeData', {
      sources: [s3deploy.Source.asset(recipeDataPath)],
      destinationBucket: dataBucket,
      destinationKeyPrefix: 'recipes_json/',
      memoryLimit: 512,
    });

    // Deploy local Corpus A docs under kb/structured/ (prune off so sync CLI upserts survive empty deploys).
    // Run `make build-kb-index` before deploy when you want CDK to push built documents.
    new s3deploy.BucketDeployment(this, 'DeployKbStructured', {
      sources: [s3deploy.Source.asset(kbStructuredPath)],
      destinationBucket: dataBucket,
      destinationKeyPrefix: 'kb/structured/',
      prune: false,
      memoryLimit: 512,
    });

    // --- Bedrock Knowledge Base (OpenSearch Serverless + Titan Embeddings V2) ---
    const recipeKb = new RecipeKnowledgeBase(this, 'RecipeKnowledgeBase', {
      dataBucket,
      structuredPrefix: 'kb/structured/',
    });

    // --- Lambda: Meal plan generator + v3 RAG chat (Retrieve then InvokeModel) ---
    const mealPlanLambda = new lambda.Function(this, 'MealPlanFunction', {
      runtime: lambda.Runtime.PYTHON_3_11,
      handler: 'lambda_function.lambda_handler',
      code: lambda.Code.fromAsset(backendPath),
      environment: {
        S3_BUCKET_NAME: dataBucket.bucketName,
        KNOWLEDGE_BASE_ID: recipeKb.knowledgeBaseId,
        GENERATOR_MODEL_ID: CLAUDE_3_5_HAIKU_MODEL_ID,
        EMBEDDING_MODEL_ID: TITAN_EMBED_TEXT_V2_MODEL_ID,
      },
      // Chat = Retrieve + Claude; 30s/256MB is too tight for worst-case latency.
      timeout: cdk.Duration.seconds(60),
      memorySize: 512,
    });
    dataBucket.grantRead(mealPlanLambda);

    mealPlanLambda.addToRolePolicy(
      new iam.PolicyStatement({
        sid: 'BedrockKnowledgeBaseRetrieve',
        actions: ['bedrock:Retrieve'],
        resources: [recipeKb.knowledgeBase.attrKnowledgeBaseArn],
      })
    );
    mealPlanLambda.addToRolePolicy(
      new iam.PolicyStatement({
        sid: 'BedrockInvokeGeneratorModel',
        actions: ['bedrock:InvokeModel'],
        resources: [
          // Direct on-demand model id (default GENERATOR_MODEL_ID).
          `arn:${this.partition}:bedrock:${this.region}::foundation-model/${CLAUDE_3_5_HAIKU_MODEL_ID}`,
          // Cross-region / application inference profiles when the account routes Claude that way.
          `arn:${this.partition}:bedrock:${this.region}:${this.account}:inference-profile/*`,
          `arn:${this.partition}:bedrock:*:${this.account}:inference-profile/*`,
        ],
      })
    );

    // --- API Gateway: REST API with CORS ---
    const api = new apigateway.RestApi(this, 'MealPlanApi', {
      restApiName: 'PantryBuddy Meal Plan API',
      description: 'API for PantryBuddy weekly meal plan generation',
      defaultCorsPreflightOptions: {
        allowOrigins: apigateway.Cors.ALL_ORIGINS,
        allowMethods: apigateway.Cors.ALL_METHODS,
        allowHeaders: ['Content-Type', 'Authorization'],
      },
      deployOptions: {
        stageName: 'prod',
      },
    });

    const lambdaIntegration = new apigateway.LambdaIntegration(mealPlanLambda);
    const v2 = api.root.addResource('v2');
    const generateMealPlan = v2.addResource('generate-meal-plan');
    generateMealPlan.addMethod('POST', lambdaIntegration);

    const v3 = api.root.addResource('v3');
    v3.addResource('chat').addMethod('POST', lambdaIntegration);
    v3.addResource('suggest-meals').addMethod('POST', lambdaIntegration);

    // --- Optional: Deploy frontend to the website bucket (run once or via CI) ---
    new s3deploy.BucketDeployment(this, 'DeployFrontend', {
      sources: [s3deploy.Source.asset(frontendPath)],
      destinationBucket: websiteBucket,
      memoryLimit: 512,
    });

    // --- Outputs ---
    new cdk.CfnOutput(this, 'WebsiteBucketName', {
      value: websiteBucket.bucketName,
      description: 'S3 bucket for static website hosting',
      exportName: 'PantryBuddy-WebsiteBucketName',
    });
    new cdk.CfnOutput(this, 'WebsiteURL', {
      value: websiteBucket.bucketWebsiteUrl,
      description: 'Static website URL (use this or CloudFront later)',
      exportName: 'PantryBuddy-WebsiteURL',
    });
    new cdk.CfnOutput(this, 'DataBucketName', {
      value: dataBucket.bucketName,
      description: 'S3 bucket for recipe JSON data and kb/structured corpus',
      exportName: 'PantryBuddy-DataBucketName',
    });
    new cdk.CfnOutput(this, 'ApiEndpoint', {
      value: api.url,
      description: 'API Gateway base URL (set API_BASE_URL in frontend config)',
      exportName: 'PantryBuddy-ApiEndpoint',
    });
    new cdk.CfnOutput(this, 'GenerateMealPlanUrl', {
      value: `${api.url}v2/generate-meal-plan`,
      description: 'Full URL for POST /v2/generate-meal-plan',
      exportName: 'PantryBuddy-GenerateMealPlanUrl',
    });
    new cdk.CfnOutput(this, 'V3ChatUrl', {
      value: `${api.url}v3/chat`,
      description: 'Full URL for POST /v3/chat (Bedrock KB Retrieve + Claude)',
      exportName: 'PantryBuddy-V3ChatUrl',
    });
    new cdk.CfnOutput(this, 'V3SuggestMealsUrl', {
      value: `${api.url}v3/suggest-meals`,
      description: 'Full URL for POST /v3/suggest-meals (NOT_IMPLEMENTED until a later slice)',
      exportName: 'PantryBuddy-V3SuggestMealsUrl',
    });
    new cdk.CfnOutput(this, 'KnowledgeBaseId', {
      value: recipeKb.knowledgeBaseId,
      description: 'Bedrock Knowledge Base ID (wired to Lambda as KNOWLEDGE_BASE_ID)',
      exportName: 'PantryBuddy-KnowledgeBaseId',
    });
    new cdk.CfnOutput(this, 'GeneratorModelId', {
      value: CLAUDE_3_5_HAIKU_MODEL_ID,
      description: 'Bedrock generator model for v3 chat (GENERATOR_MODEL_ID)',
      exportName: 'PantryBuddy-GeneratorModelId',
    });
    new cdk.CfnOutput(this, 'KnowledgeBaseDataSourceId', {
      value: recipeKb.dataSourceId,
      description: 'Bedrock data source ID for kb/structured/ ingestion',
      exportName: 'PantryBuddy-KnowledgeBaseDataSourceId',
    });
    new cdk.CfnOutput(this, 'KbSyncRoleArn', {
      value: recipeKb.syncRole.roleArn,
      description: 'IAM role for S3 kb/structured upload + StartIngestionJob (tools/sync_kb_index.py)',
      exportName: 'PantryBuddy-KbSyncRoleArn',
    });
    new cdk.CfnOutput(this, 'EmbeddingModelId', {
      value: TITAN_EMBED_TEXT_V2_MODEL_ID,
      description: 'Embedding model used by the Knowledge Base',
      exportName: 'PantryBuddy-EmbeddingModelId',
    });
  }
}
